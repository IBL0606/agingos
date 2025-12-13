from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models.rule import Rule, RuleType
from models.deviation import Deviation, DeviationStatus
from models.db_event import EventDB

logger = logging.getLogger("rule_engine")


def run_rules(db: Session, now: datetime | None = None):
    """
    Kjør alle aktive regler.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    rules = db.query(Rule).filter(Rule.is_enabled == True).all()

    for rule in rules:
        if rule.rule_type == RuleType.NO_MOTION:
            evaluate_no_motion_rule(db, rule, now)

    db.commit()


def _within_active_hours(now: datetime, active_hours: list[int]) -> bool:
    """
    Sjekker om nåværende tidspunkt er innenfor aktive timer.
    active_hours = [start_hour, end_hour]
    """
    start_hour, end_hour = active_hours
    return start_hour <= now.hour < end_hour


def evaluate_no_motion_rule(db: Session, rule: Rule, now: datetime):
    """
    Evaluerer én NO_MOTION-regel.
    """
    params = rule.params or {}

    # LOGGER: params dump
    logger.warning(f"[NO_MOTION] rule_id={rule.id} params={params}")

    window_minutes = int(params.get("window_minutes", 60))
    active_hours = params.get("active_hours", [0, 24])
    source = params.get("source")

    if not source:
        # LOGGER: missing source
        logger.warning("[NO_MOTION] return: missing source")
        return

    if not _within_active_hours(now, active_hours):
        # LOGGER: outside active hours
        logger.warning(
            f"[NO_MOTION] return: outside active_hours now={now.isoformat()} active_hours={active_hours}"
        )
        return

    cutoff = now - timedelta(minutes=window_minutes)

    last_motion = (
        db.query(EventDB)
        .filter(EventDB.source == source)
        .filter(EventDB.type == "motion")
        .filter(EventDB.value == "on")
        .order_by(EventDB.timestamp.desc())
        .first()
    )

    if not last_motion:
        # LOGGER: no last_motion
        logger.warning("[NO_MOTION] return: no last_motion found")
        return

    last_ts = last_motion.timestamp
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)

    if last_ts >= cutoff:
        # LOGGER: last motion is recent enough
        logger.warning(
            f"[NO_MOTION] return: last_ts>=cutoff last_ts={last_ts.isoformat()} cutoff={cutoff.isoformat()}"
        )
        return

    # LOGGER: trigger deviation
    logger.warning(
        f"[NO_MOTION] TRIGGER deviation: last_ts={last_ts.isoformat()} cutoff={cutoff.isoformat()} source={source}"
    )

    _upsert_deviation(
        db=db,
        rule=rule,
        now=now,
        subject_key=source,
        context={
            "reason": "no_motion",
            "window_minutes": window_minutes,
            "active_hours": active_hours,
        },
        evidence={
            "last_motion_at": last_ts.isoformat(),
        },
    )


def _upsert_deviation(
    db: Session,
    rule: Rule,
    now: datetime,
    subject_key: str,
    context: dict,
    evidence: dict,
):
    """
    Oppretter eller oppdaterer et OPEN deviation for (rule, subject_key).
    """
    existing = (
        db.query(Deviation)
        .filter(Deviation.rule_id == rule.id)
        .filter(Deviation.subject_key == subject_key)
        .filter(Deviation.status == DeviationStatus.OPEN)
        .one_or_none()
    )

    if existing:
        existing.last_seen_at = now
        existing.context = context
        existing.evidence = evidence
        return

    dev = Deviation(
        rule_id=rule.id,
        status=DeviationStatus.OPEN,
        severity=rule.severity,
        started_at=now,
        last_seen_at=now,
        subject_key=subject_key,
        context=context,
        evidence=evidence,
    )
    db.add(dev)
