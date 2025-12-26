from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import json
import logging
import os
import sys
import time
import traceback
import uuid

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from util.time import utcnow
from db import SessionLocal
from services.rule_engine import RULE_REGISTRY
from config.rule_config import load_rule_config

from models.rule import Rule, RuleType
from models.deviation import Deviation, DeviationStatus


scheduler = BackgroundScheduler()

logger = logging.getLogger("scheduler")

# Ensure JSONL (message-only) output for this logger, without duplicate propagation.
if not logger.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)
logger.propagate = False


# Debug toggle: allow more verbose logging locally, but still never log secrets.
_DEBUG_LOG_PAYLOADS = os.getenv("AGINGOS_DEBUG_LOG_PAYLOADS", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# Deny-list of keys that should never be logged raw.
_DENY_KEYS = {
    "payload",
    "body",
    "request_body",
    "headers",
    "authorization",
    "x-api-key",
    "api_key",
    "token",
    "password",
    "secret",
    "database_url",
}


def _truncate_str(s: str, max_len: int = 800) -> str:
    return s if len(s) <= max_len else s[:max_len] + "...<truncated>"


def _sanitize_value(v: Any, depth: int = 0, max_depth: int = 3) -> Any:
    """
    Best-effort sanitizer to avoid huge logs and accidental leakage.
    Note: deny-list keys are handled by _log_event() itself.
    """
    if depth > max_depth:
        return "<max_depth>"

    if v is None or isinstance(v, (int, float, bool)):
        return v

    if isinstance(v, str):
        return _truncate_str(v)

    if isinstance(v, list):
        return [_sanitize_value(x, depth + 1, max_depth) for x in v[:50]]

    if isinstance(v, dict):
        out: dict[str, Any] = {}
        for k, vv in v.items():
            lk = str(k).lower()
            if lk in _DENY_KEYS:
                out[str(k)] = "<redacted>"
            else:
                out[str(k)] = _sanitize_value(vv, depth + 1, max_depth)
        return out

    return _truncate_str(str(v))


def _utc_iso(dt: datetime) -> str:
    # Expecting aware UTC datetimes from utcnow(); keep a stable "Z" format.
    s = dt.isoformat()
    return s.replace("+00:00", "Z")


def _log_event(
    *,
    level: str,
    event: str,
    run_id: str,
    msg: str,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "ts": _utc_iso(utcnow()),
        "level": level,
        "component": "scheduler",
        "event": event,
        "run_id": run_id,
        "msg": msg,
    }

    safe_fields: dict[str, Any] = {}
    for k, v in fields.items():
        lk = str(k).lower()

        # Never log deny-list fields in normal drift.
        if lk in _DENY_KEYS and not _DEBUG_LOG_PAYLOADS:
            continue

        # Even in debug, do not log raw deny-list values.
        if lk in _DENY_KEYS:
            safe_fields[k] = "<redacted>"
            continue

        safe_fields[k] = _sanitize_value(v)

    payload.update(safe_fields)

    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    lvl = (level or "").upper()
    if lvl == "ERROR":
        logger.error(line)
    elif lvl == "WARN" or lvl == "WARNING":
        logger.warning(line)
    else:
        logger.info(line)


def _severity_str_to_int(s: str) -> int:
    v = (s or "").upper()
    if v == "LOW":
        return 1
    if v == "HIGH":
        return 3
    # Default: MEDIUM / ukjent
    return 2


def _get_or_create_rule_row(db: Session, rule_key: str) -> Rule:
    # Vi bruker Rule.name som string-key ("R-002", osv.) og mapper til FK via Rule.id.
    existing = db.query(Rule).filter(Rule.name == rule_key).one_or_none()
    if existing:
        return existing

    # Bro-løsning: RuleType har foreløpig kun NO_MOTION i modellen.
    # Vi bruker den som placeholder for alle registry-regler, og lar name være identiteten.
    r = Rule(
        name=rule_key,
        is_enabled=True,
        rule_type=RuleType.NO_MOTION,
        params={},
        severity=2,
    )
    db.add(r)
    db.flush()  # få r.id
    return r


def _upsert_open_deviation(
    db: Session,
    rule_row: Rule,
    subject_key: str,
    now: datetime,
    deviation_v1: dict,
) -> None:
    existing = (
        db.query(Deviation)
        .filter(Deviation.rule_id == rule_row.id)
        .filter(Deviation.subject_key == subject_key)
        .filter(Deviation.status.in_([DeviationStatus.OPEN, DeviationStatus.ACK]))
        .one_or_none()
    )

    context = {
        "rule_key": deviation_v1["rule_id"],
        "title": deviation_v1["title"],
        "explanation": deviation_v1["explanation"],
        "window": deviation_v1["window"],
        "timestamp": deviation_v1["timestamp"],
        "severity_str": deviation_v1["severity"],
    }

    evidence = {
        "event_ids": deviation_v1.get("evidence", []),
    }

    if existing:
        existing.last_seen_at = now
        existing.context = context
        existing.evidence = evidence
        # severity kan endres i fremtiden; oppdater for konsistens
        existing.severity = _severity_str_to_int(deviation_v1["severity"])
        return

    dev = Deviation(
        rule_id=rule_row.id,
        status=DeviationStatus.OPEN,
        severity=_severity_str_to_int(deviation_v1["severity"]),
        started_at=now,
        last_seen_at=now,
        subject_key=subject_key,
        context=context,
        evidence=evidence,
    )
    db.add(dev)


def _close_stale_deviations(
    db: Session,
    *,
    subject_key: str,
    now: datetime,
) -> int:
    """
    Close deviations that have not been seen within expire_after_minutes.

    Policy:
    - Applies to status OPEN or ACK.
    - Only for the current subject_key (thin-slice: default subject).
    - Uses per-rule expire_after_minutes from rules.yaml via RuleConfig.
    """
    cfg = load_rule_config()
    closed_count = 0

    candidates = (
        db.query(Deviation)
        .filter(Deviation.subject_key == subject_key)
        .filter(Deviation.status.in_([DeviationStatus.OPEN, DeviationStatus.ACK]))
        .all()
    )

    for dev in candidates:
        # rules.yaml keys are the rule "key" like "R-002". In DB that is Rule.name.
        rule_key = dev.rule.name if dev.rule else None
        if not rule_key:
            continue

        expire_minutes = cfg.rule_expire_after_minutes(rule_key)
        cutoff = now - timedelta(minutes=expire_minutes)

        if dev.last_seen_at < cutoff:
            dev.status = DeviationStatus.CLOSED
            closed_count += 1

    return closed_count


def run_rule_engine_job():
    run_id = str(uuid.uuid4())
    t0 = time.monotonic()

    db = SessionLocal()
    try:
        cfg = load_rule_config()
        interval_minutes = cfg.scheduler_interval_minutes()
        subject_key = cfg.scheduler_default_subject_key()

        now = utcnow()
        until = now
        since = now - timedelta(minutes=interval_minutes)

        _log_event(
            level="INFO",
            event="scheduler_run_start",
            run_id=run_id,
            msg="scheduler run started",
            interval_minutes=interval_minutes,
            since=_utc_iso(since),
            until=_utc_iso(until),
        )

        # Finn hvilke regler som faktisk kjøres av scheduler (enabled_in_scheduler=true)
        enabled_rule_ids = [
            rid for rid in RULE_REGISTRY.keys() if cfg.rule_enabled_in_scheduler(rid)
        ]

        deviations_upserted = 0
        rules_total = len(enabled_rule_ids)
        rules_ok = 0
        rules_failed = 0

        for rid in enabled_rule_ids:
            t_rule0 = time.monotonic()

            lookback = cfg.rule_lookback_minutes(rid)
            r_since = now - timedelta(minutes=lookback)
            r_until = now

            _log_event(
                level="INFO",
                event="scheduler_rule_start",
                run_id=run_id,
                msg="rule evaluation started",
                rule_id=rid,
                subject_key=subject_key,
                since=_utc_iso(r_since),
                until=_utc_iso(r_until),
            )

            try:
                upserted_for_rule = 0

                with db.begin_nested():
                    spec = RULE_REGISTRY[rid]
                    rule_devs = spec.eval_fn(db, since=r_since, until=r_until, now=now)

                    # Persist alle avvik fra regelen (kan være 0..N)
                    rule_row = _get_or_create_rule_row(db, rule_key=rid)

                    for d in rule_devs:
                        dct = d.model_dump(mode="json")
                        _upsert_open_deviation(
                            db,
                            rule_row=rule_row,
                            subject_key=subject_key,
                            now=now,
                            deviation_v1=dct,
                        )
                        upserted_for_rule += 1

                deviations_upserted += upserted_for_rule
                rules_ok += 1

                duration_ms = int((time.monotonic() - t_rule0) * 1000)

                _log_event(
                    level="INFO",
                    event="scheduler_rule_result",
                    run_id=run_id,
                    msg="rule evaluation finished",
                    rule_id=rid,
                    duration_ms=duration_ms,
                    counts={
                        "evaluated": 1,
                        "deviations_upserted": upserted_for_rule,
                        "deviations_closed": 0,
                    },
                )
            except Exception as e:
                rules_failed += 1
                duration_ms = int((time.monotonic() - t_rule0) * 1000)

                _log_event(
                    level="ERROR",
                    event="scheduler_rule_error",
                    run_id=run_id,
                    msg="rule evaluation failed",
                    rule_id=rid,
                    subject_key=subject_key,
                    duration_ms=duration_ms,
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                        "stacktrace": traceback.format_exc(),
                    },
                )
                continue

        closed = _close_stale_deviations(db, subject_key=subject_key, now=now)

        db.commit()

        duration_ms = int((time.monotonic() - t0) * 1000)

        _log_event(
            level="INFO",
            event="scheduler_run_end",
            run_id=run_id,
            msg="scheduler run finished",
            duration_ms=duration_ms,
            counts={
                "rules_total": rules_total,
                "rules_ok": rules_ok,
                "rules_failed": rules_failed,
                "deviations_upserted": deviations_upserted,
                "deviations_closed": closed,
            },
        )

    except Exception as e:
        db.rollback()
        duration_ms = int((time.monotonic() - t0) * 1000)
        _log_event(
            level="ERROR",
            event="scheduler_run_end",
            run_id=run_id,
            msg="scheduler run failed",
            duration_ms=duration_ms,
            error={
                "type": type(e).__name__,
                "message": str(e),
                "stacktrace": traceback.format_exc(),
            },
        )
    finally:
        db.close()


def setup_scheduler():
    cfg = load_rule_config()
    interval_minutes = cfg.scheduler_interval_minutes()

    # This is still useful on startup.
    run_id = "startup"
    _log_event(
        level="INFO",
        event="scheduler_configured",
        run_id=run_id,
        msg="scheduler configured",
        interval_minutes=interval_minutes,
    )

    scheduler.add_job(
        run_rule_engine_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="rule_engine_job",
        replace_existing=True,
    )
