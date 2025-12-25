from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import logging

from datetime import datetime, timedelta

from util.time import utcnow
from services.rule_engine import evaluate_rules_for_scheduler
from db import SessionLocal
from config.rule_config import load_rule_config

from models.rule import Rule, RuleType
from models.deviation import Deviation, DeviationStatus

scheduler = BackgroundScheduler()

logger = logging.getLogger("scheduler")


def _severity_str_to_int(s: str) -> int:
    v = (s or "").upper()
    if v == "LOW":
        return 1
    if v == "HIGH":
        return 3
    # Default: MEDIUM / ukjent
    return 2


def _get_or_create_rule_row(
    db: SessionLocal.__annotations__.get("return", object), rule_key: str
) -> Rule:
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
    db: SessionLocal.__annotations__.get("return", object),
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
    db: SessionLocal.__annotations__.get("return", object),
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
    db = SessionLocal()
    try:
        cfg = load_rule_config()
        subject_key = cfg.scheduler_default_subject_key()
        now = utcnow()
        devs = evaluate_rules_for_scheduler(db, now=now)
        logger.info(f"Scheduler run: computed {len(devs)} deviation(s)")

        # Persist: upsert OPEN/ACK deviation per (rule_key, subject_key)
        for d in devs:
            # d er DeviationV1 (pydantic). Vi jobber med dict for JSON-feltene i DB.
            dct = d.model_dump(mode="json")
            rule_key = dct["rule_id"]

            rule_row = _get_or_create_rule_row(db, rule_key=rule_key)
            _upsert_open_deviation(
                db,
                rule_row=rule_row,
                subject_key=subject_key,
                now=now,
                deviation_v1=dct,
            )

        closed = _close_stale_deviations(db, subject_key=subject_key, now=now)
        if closed:
            logger.info(f"Scheduler run: closed {closed} stale deviation(s)")

        db.commit()
    finally:
        db.close()


def setup_scheduler():
    cfg = load_rule_config()
    interval_minutes = cfg.scheduler_interval_minutes()
    logger.info(f"Scheduler configured: interval_minutes={interval_minutes}")

    scheduler.add_job(
        run_rule_engine_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="rule_engine_job",
        replace_existing=True,
    )
