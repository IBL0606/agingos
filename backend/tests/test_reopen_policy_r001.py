from __future__ import annotations

from datetime import datetime, timezone, timedelta

from db import SessionLocal
from models.deviation import Deviation, DeviationStatus
from models.rule import Rule
from services.scheduler import run_rule_engine_job


def _freeze_scheduler_utcnow(now_utc: datetime) -> None:
    import services.scheduler as scheduler

    def _frozen():
        return now_utc

    scheduler.utcnow = _frozen  # type: ignore[assignment]


def test_reopen_policy_creates_new_open_after_closed():
    # Pick a far-future time where there are no events in DB => R-001 NO_MOTION should trigger.
    t0 = datetime(2099, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=6)

    db = SessionLocal()
    try:
        r001 = db.query(Rule).filter(Rule.name == "R-001").first()
        assert r001 is not None
        rule_pk = r001.id  # INTEGER PK referenced by deviations.rule_id

        # 1) Run scheduler at t0 -> should create OPEN
        _freeze_scheduler_utcnow(t0)
        run_rule_engine_job()

        latest_open = (
            db.query(Deviation)
            .filter(Deviation.rule_id == rule_pk)
            .filter(Deviation.org_id == "default")
            .filter(Deviation.home_id == "default")
            .filter(Deviation.subject_id == "default")
            .filter(Deviation.status == DeviationStatus.OPEN)
            .order_by(Deviation.id.desc())
            .first()
        )
        assert latest_open is not None

        # 2) Close it
        latest_open.status = DeviationStatus.CLOSED
        db.commit()
        closed_id = latest_open.id

        # 3) Run scheduler later -> should create NEW OPEN row (reopen)
        _freeze_scheduler_utcnow(t1)
        run_rule_engine_job()

        reopened = (
            db.query(Deviation)
            .filter(Deviation.rule_id == rule_pk)
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
