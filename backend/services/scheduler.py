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
from sqlalchemy import text

from util.time import utcnow
from db import SessionLocal
from services.rule_engine import RULE_REGISTRY
from services.proposals_miner import run_proposals_miner_job
from services.proposals_expiry import run_proposals_expiry_job
from config.rule_config import load_rule_config

from models.rule import Rule, RuleType
from models.deviation import Deviation, DeviationStatus


scheduler = BackgroundScheduler()

logger = logging.getLogger("scheduler")

ANOMALIES_RUNNER_STATUS = {
    "last_run_at": None,
    "last_ok_at": None,
    "last_error_at": None,
    "last_error_msg": None,
    "last_scored_bucket_start": None,
    "last_counts": None,
    "last_rooms_scored": None,
}


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

    ev = deviation_v1.get("evidence")

    # evidence kan være enten list (legacy) eller dict (v1)
    if isinstance(ev, dict):
        event_ids = ev.get("event_ids", [])
        extra = {k: v for k, v in ev.items() if k != "event_ids"}
    elif isinstance(ev, list):
        event_ids = ev
        extra = {}
    else:
        event_ids = []
        extra = {}

    evidence = {"event_ids": event_ids, **extra}

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
        rule_key = getattr(dev, "rule_id", None) or getattr(dev, "rule_key", None)
        if not rule_key:
            continue

        expire_minutes = cfg.rule_expire_after_minutes(rule_key)
        cutoff = now - timedelta(minutes=expire_minutes)

        if dev.last_seen_at < cutoff:
            dev.status = DeviationStatus.CLOSED
            closed_count += 1

    return closed_count


def _get_monitor_mode(db, *, monitor_key: str, room_id: str = "__GLOBAL__") -> str:
    try:
        row = (
            db.execute(
                text(
                    "SELECT mode FROM monitor_modes WHERE monitor_key=:k AND room_id=:r"
                ),
                {"k": monitor_key, "r": room_id},
            )
            .mappings()
            .one_or_none()
        )
        if row and row.get("mode") in ("OFF", "TEST", "ON"):
            return row["mode"]
    except Exception:
        pass
    return "ON"


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

                    mode = _get_monitor_mode(db, monitor_key=rid, room_id="__GLOBAL__")
                    if mode == "OFF":
                        rule_devs = []

                    # Persist alle avvik fra regelen (kan være 0..N)
                    rule_row = _get_or_create_rule_row(db, rule_key=rid)

                    for d in rule_devs:
                        dct = d.model_dump(mode="json")
                        if mode == "TEST":
                            # Persist stable marker on evidence (without dropping event_ids).
                            ev = dct.get("evidence")
                            if isinstance(ev, dict):
                                ev["_monitor_mode"] = "TEST"
                            elif isinstance(ev, list):
                                dct["evidence"] = {
                                    "event_ids": ev,
                                    "_monitor_mode": "TEST",
                                }
                            else:
                                dct["evidence"] = {
                                    "event_ids": [],
                                    "_monitor_mode": "TEST",
                                }

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


def run_anomalies_job_safe():
    """Fail-safe wrapper for APScheduler: never raise; updates in-memory status; always logs."""
    from datetime import datetime, timezone
    import traceback

    ANOMALIES_RUNNER_STATUS["last_run_at"] = datetime.now(timezone.utc).isoformat()

    try:
        out = run_anomalies_job()

        ANOMALIES_RUNNER_STATUS["last_ok_at"] = datetime.now(timezone.utc).isoformat()
        ANOMALIES_RUNNER_STATUS["last_error_at"] = None
        ANOMALIES_RUNNER_STATUS["last_error_msg"] = None
        ANOMALIES_RUNNER_STATUS["last_scored_bucket_start"] = (
            out.get("bucket_start").isoformat() if out.get("bucket_start") else None
        )
        ANOMALIES_RUNNER_STATUS["last_counts"] = out.get("counts")
        ANOMALIES_RUNNER_STATUS["last_rooms_scored"] = out.get("rooms_scored")

        _log_event(
            level="INFO",
            event="anomalies_runner_tick",
            run_id=out.get("run_id"),
            msg="anomalies runner tick",
            bucket_start=(
                out.get("bucket_start").isoformat() if out.get("bucket_start") else None
            ),
            rooms_scored=out.get("rooms_scored"),
            counts=out.get("counts"),
        )
    except Exception as e:
        ANOMALIES_RUNNER_STATUS["last_error_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        ANOMALIES_RUNNER_STATUS["last_error_msg"] = str(e)

        _log_event(
            level="ERROR",
            event="anomalies_runner_error",
            run_id="n/a",
            msg="anomalies runner failed",
            error={
                "type": type(e).__name__,
                "message": str(e),
                "stacktrace": traceback.format_exc(),
            },
        )
        return


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

    scheduler.add_job(
        run_anomalies_job_safe,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="anomalies_job",
        replace_existing=True,
    )

    scheduler.add_job(
        run_proposals_miner_job,
        trigger=IntervalTrigger(hours=24),
        id="proposals_miner_job",
        replace_existing=True,
    )

    scheduler.add_job(
        run_proposals_expiry_job,
        trigger=IntervalTrigger(minutes=10),
        id="proposals_expiry_job",
        replace_existing=True,
    )


# --- Anomalies runner (ID003_10) ---
# Minimal deterministic runner helpers. Wiring into APScheduler comes in a later step.


def run_anomalies_job_one(
    db,
    *,
    room: str,
    bucket_start,
    close_after_green_buckets: int = 2,
    pet_weight: float = 0.25,
    unknown_weight: float = 0.50,
) -> dict:
    """
    Score exactly one (room, bucket_start) and persist lifecycle via upsert_bucket_result.
    Deterministic given explicit args. Intended to be used by scheduler-job later.
    """
    from datetime import datetime

    # Parse bucket_start if string (accept Z)
    dt = bucket_start
    if isinstance(bucket_start, str):
        bs = bucket_start.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(bs)

    from services.anomaly_scoring import score_room_bucket
    from services.anomalies_repo_lifecycle import upsert_bucket_result

    scored = score_room_bucket(
        db,
        room=room,
        bucket_start=dt,
        pet_weight=pet_weight,
        unknown_weight=unknown_weight,
    )

    ep = upsert_bucket_result(
        db,
        room=scored.room,
        bucket_start=scored.bucket_start,
        bucket_end=scored.bucket_end,
        score_total=float(scored.score_total),
        level=scored.level,
        reasons=scored.reasons,
        reasons_summary=(scored.details if hasattr(scored, "details") else None),
        close_green_n=close_after_green_buckets,
        close_timeout_minutes=90,
    )

    if ep is None:
        proc_action = "NOOP"
        proc_episode_id = None
        proc_active = False
    else:
        if bool(getattr(ep, "_noop", False)):
            proc_action = "NOOP"
        elif not bool(getattr(ep, "active", True)):
            proc_action = "CLOSE"
        elif int(getattr(ep, "bucket_count", 0) or 0) <= 1:
            proc_action = "OPEN"
        else:
            proc_action = "UPDATE"
        proc_episode_id = ep.id
        proc_active = bool(getattr(ep, "active", True))

    return {
        "room": scored.room,
        "bucket_start": scored.bucket_start,
        "bucket_end": scored.bucket_end,
        "level": scored.level,
        "score_total": float(scored.score_total),
        "action": proc_action,
        "episode_id": proc_episode_id,
        "active": proc_active,
    }


def run_anomalies_job_deterministic() -> dict:
    """
    Debug helper: scores ONE room+bucket from env (or defaults) using a fresh DB session.
    Useful for verifying import-paths and lifecycle without wiring into scheduler yet.
    """
    import os
    from db import SessionLocal

    room = os.environ.get("ANOMALY_TEST_ROOM", "soverom")
    bucket_start = os.environ.get("ANOMALY_TEST_BUCKET_START", "2026-02-05T05:15:00Z")

    db = SessionLocal()
    try:
        res = run_anomalies_job_one(db, room=room, bucket_start=bucket_start)
        db.commit()
        return {"ok": True, "result": res}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def _anomaly_pick_one_room_id(db) -> str:
    """Deterministic: pick one known room_id from baseline_room_bucket (min(room_id))."""
    from sqlalchemy import text

    row = (
        db.execute(text("SELECT MIN(room_id) AS room_id FROM baseline_room_bucket"))
        .mappings()
        .first()
    )
    rid = row.get("room_id") if row else None
    if not rid:
        raise RuntimeError("No baseline_room_bucket rows -> cannot pick room_id")
    return str(rid)


def run_anomalies_job_one_deterministic_room(db, *, bucket_start) -> dict:
    """Deterministic: pick room_id from baseline_room_bucket and score one bucket."""
    room_id = _anomaly_pick_one_room_id(db)
    return run_anomalies_job_one(db, room=room_id, bucket_start=bucket_start)


def _latest_finished_bucket_start_utc(*, bucket_minutes: int = 15):
    """Return last finished bucket_start in UTC, aligned by Europe/Oslo local time (DST-safe)."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    if bucket_minutes <= 0:
        raise ValueError("bucket_minutes must be > 0")

    oslo = ZoneInfo("Europe/Oslo")
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(oslo)

    # floor to bucket boundary in LOCAL time
    m = now_local.minute
    floored_minute = (m // bucket_minutes) * bucket_minutes
    floored_local = now_local.replace(minute=floored_minute, second=0, microsecond=0)

    # last finished bucket start is previous bucket boundary
    latest_finished_local = floored_local - timedelta(minutes=bucket_minutes)

    # return as UTC-aware
    return latest_finished_local.astimezone(timezone.utc)


def run_anomalies_job_latest_one() -> dict:
    """Debug helper: pick deterministic room_id and score the latest finished bucket."""
    from db import SessionLocal

    bs = _latest_finished_bucket_start_utc()
    db = SessionLocal()
    try:
        room_id = _anomaly_pick_one_room_id(db)
        res = run_anomalies_job_one(db, room=room_id, bucket_start=bs)
        db.commit()
        return {"ok": True, "room": room_id, "bucket_start": bs, "result": res}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def _anomaly_list_room_ids(db) -> list[str]:
    """List known rooms for anomaly scoring. Source: baseline_room_bucket (latest model_end per user)."""
    from sqlalchemy import text

    row = (
        db.execute(text("SELECT id::text AS id FROM app_instance LIMIT 1"))
        .mappings()
        .first()
    )
    if not row or not row.get("id"):
        raise RuntimeError("app_instance missing (cannot resolve user_id)")
    uid = row["id"]

    me = (
        db.execute(
            text(
                """
            SELECT model_end
            FROM baseline_model_status
            WHERE user_id = CAST(:uid AS uuid)
            ORDER BY model_end DESC
            LIMIT 1
            """
            ),
            {"uid": uid},
        )
        .mappings()
        .first()
    )
    model_end = me["model_end"] if me else None
    if not model_end:
        return []

    rooms = (
        db.execute(
            text(
                """
            SELECT DISTINCT room_id
            FROM baseline_room_bucket
            WHERE user_id = CAST(:uid AS uuid)
              AND model_end = :model_end
            ORDER BY room_id ASC
            """
            ),
            {"uid": uid, "model_end": model_end},
        )
        .mappings()
        .all()
    )
    return [str(r["room_id"]) for r in rooms if r.get("room_id")]


def run_anomalies_job() -> dict:
    """
    Scheduler job: score latest finished 15-min bucket (Europe/Oslo aligned) for each room.
    Idempotent via lifecycle upsert (NOOP when already processed).
    """
    from datetime import datetime, timezone
    import uuid
    from db import SessionLocal

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    bucket_start = _latest_finished_bucket_start_utc()

    db = SessionLocal()
    counts = {"OPEN": 0, "UPDATE": 0, "CLOSE": 0, "NOOP": 0, "ERROR": 0}
    rooms_scored = 0
    try:
        rooms = _anomaly_list_room_ids(db)
        for room_id in rooms:
            try:
                res = run_anomalies_job_one(db, room=room_id, bucket_start=bucket_start)
                rooms_scored += 1
                a = str(res.get("action") or "NOOP").upper()
                if a not in counts:
                    a = "NOOP"
                counts[a] += 1
            except Exception:
                counts["ERROR"] += 1
                # keep going; one room must not crash whole run
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # log summary in scheduler logger (JSONL style like existing scheduler)
    try:
        logger.info(
            "",
            extra={
                "component": "scheduler",
                "event": "anomalies_runner_summary",
                "run_id": run_id,
                "started_at": started_at.isoformat(),
                "bucket_start": bucket_start.isoformat(),
                "rooms_scored": rooms_scored,
                **{f"count_{k.lower()}": v for k, v in counts.items()},
            },
        )
    except Exception:
        pass

    return {
        "run_id": run_id,
        "bucket_start": bucket_start,
        "rooms_scored": rooms_scored,
        "counts": counts,
    }
