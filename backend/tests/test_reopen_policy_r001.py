from __future__ import annotations

from services.scheduler import run_rule_engine_job
from db import SessionLocal
from models.deviation import Deviation, DeviationStatus
from models.rule import Rule, RuleType


def test_reopen_policy_creates_new_open_after_closed():
    db = SessionLocal()
    try:
        # Find a NO_MOTION rule that already has deviations in this scope
        rule = (
            db.query(Rule)
            .join(Deviation, Deviation.rule_id == Rule.id)
            .filter(Rule.rule_type == RuleType.NO_MOTION)
            .filter(Deviation.org_id == "default")
            .filter(Deviation.home_id == "default")
            .filter(Deviation.subject_id == "default")
            .order_by(Rule.id.desc())
            .first()
        )
        assert rule is not None

        latest = (
            db.query(Deviation)
            .filter(Deviation.rule_id == rule.id)
            .filter(Deviation.org_id == "default")
            .filter(Deviation.home_id == "default")
            .filter(Deviation.subject_id == "default")
            .order_by(Deviation.id.desc())
            .first()
        )
        assert latest is not None

        latest.status = DeviationStatus.CLOSED
        db.commit()
        closed_id = latest.id

        run_rule_engine_job()

        reopened = (
            db.query(Deviation)
            .filter(Deviation.rule_id == rule.id)
            .filter(Deviation.org_id == "default")
            .filter(Deviation.home_id == "default")
            .filter(Deviation.subject_id == "default")
            .filter(Deviation.status == DeviationStatus.OPEN)
            .order_by(Deviation.id.desc())
            .first()
        )
        assert reopened is not None
        assert reopened.id > closed_id
    finally:
        db.close()
