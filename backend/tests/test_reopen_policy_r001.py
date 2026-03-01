from __future__ import annotations

from datetime import datetime, timezone, timedelta

from db import SessionLocal
from models.deviation import Deviation, DeviationStatus
from models.rule import Rule, RuleType


TEST_ORG = "test"
TEST_HOME = "test"
TEST_SUBJECT = "test"
TEST_SUBJECT_KEY = "test"


def _ensure_rule(db, rule_key: str) -> Rule:
    r = db.query(Rule).filter(Rule.name == rule_key).one_or_none()
    if r:
        return r
    r = Rule(
        name=rule_key,
        is_enabled=True,
        rule_type=RuleType.NO_MOTION,
        params={},
        severity=2,
    )
    db.add(r)
    db.flush()
    return r


def _cleanup(db, rule_id: int) -> None:
    # Only delete test-scope rows (never touch default/pilot scope)
    (
        db.query(Deviation)
        .filter(Deviation.rule_id == rule_id)
        .filter(Deviation.subject_key == TEST_SUBJECT_KEY)
        .filter(Deviation.org_id == TEST_ORG)
        .filter(Deviation.home_id == TEST_HOME)
        .filter(Deviation.subject_id == TEST_SUBJECT)
        .delete(synchronize_session=False)
    )
    db.commit()


def test_reopen_policy_creates_new_open_after_closed():
    """
    Reopen policy in this system = "new OPEN row after CLOSED" (partial unique index only applies to OPEN/ACK).
    This test is intentionally DB-only to avoid scheduler scope picking and event-dependencies.
    """
    db = SessionLocal()
    try:
        rule = _ensure_rule(db, "R-001")
        _cleanup(db, rule.id)

        now = datetime.now(timezone.utc)
        now2 = now + timedelta(minutes=1)

        # 1) Create OPEN
        dev1 = Deviation(
            rule_id=rule.id,
            status=DeviationStatus.OPEN,
            severity=2,
            started_at=now,
            last_seen_at=now,
            subject_key=TEST_SUBJECT_KEY,
            org_id=TEST_ORG,
            home_id=TEST_HOME,
            subject_id=TEST_SUBJECT,
            context={
                "rule_key": "R-001",
                "title": "x",
                "explanation": "x",
                "window": {},
                "timestamp": now.isoformat(),
                "severity_str": "MEDIUM",
            },
            evidence={"event_ids": []},
        )
        db.add(dev1)
        db.commit()
        db.refresh(dev1)

        # 2) Close it
        dev1.status = DeviationStatus.CLOSED
        db.commit()
        closed_id = dev1.id

        # 3) New OPEN row after CLOSED (reopen)
        dev2 = Deviation(
            rule_id=rule.id,
            status=DeviationStatus.OPEN,
            severity=2,
            started_at=now2,
            last_seen_at=now2,
            subject_key=TEST_SUBJECT_KEY,
            org_id=TEST_ORG,
            home_id=TEST_HOME,
            subject_id=TEST_SUBJECT,
            context={
                "rule_key": "R-001",
                "title": "x2",
                "explanation": "x2",
                "window": {},
                "timestamp": now2.isoformat(),
                "severity_str": "MEDIUM",
            },
            evidence={"event_ids": []},
        )
        db.add(dev2)
        db.commit()
        db.refresh(dev2)

        assert dev2.id > closed_id

        rows = (
            db.query(Deviation)
            .filter(Deviation.rule_id == rule.id)
            .filter(Deviation.subject_key == TEST_SUBJECT_KEY)
            .filter(Deviation.org_id == TEST_ORG)
            .filter(Deviation.home_id == TEST_HOME)
            .filter(Deviation.subject_id == TEST_SUBJECT)
            .order_by(Deviation.id.asc())
            .all()
        )
        assert any(r.status == DeviationStatus.CLOSED for r in rows)
        assert any(r.status == DeviationStatus.OPEN for r in rows)

    finally:
        try:
            # best-effort cleanup (test-scope only)
            rule = db.query(Rule).filter(Rule.name == "R-001").one_or_none()
            if rule:
                _cleanup(db, rule.id)
        finally:
            db.close()
