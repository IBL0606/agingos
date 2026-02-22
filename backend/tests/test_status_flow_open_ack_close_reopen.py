"""
T-0303: Statusflyt-test (OPEN → ACK → stale CLOSE → trigger reopens)

Scenario navn: "status_flow_open_ack_close_reopen"

Given/When/Then er skrevet eksplisitt i testen for å gjøre livssyklusreglene etterprøvbare.
"""

try:
    # Repo/host layout
    from backend.db import SessionLocal  # type: ignore
except Exception:
    # Container layout (/app/db.py)
    from db import SessionLocal  # type: ignore
try:
    from backend.models.rule import Rule, RuleType  # type: ignore
except Exception:
    from models.rule import Rule, RuleType  # type: ignore
try:
    from backend.models.deviation import Deviation, DeviationStatus  # type: ignore
except Exception:
    from models.deviation import Deviation, DeviationStatus  # type: ignore

# NOTE: Vi tester selve statusflyten i DB-laget (ikke rule evaluation), fordi T-0303 handler om
# livssyklus/robusthet: OPEN -> ACK -> stale CLOSE -> trigger reopens.


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


def test_status_flow_open_ack_stale_close_trigger_reopens():
    db = SessionLocal()
    try:
        subject_key = "default"
        rule_key = "R-002"

        # Given: regel finnes
        rule_row = _ensure_rule(db, rule_key)

        from util.time import utcnow

        now = utcnow()

        # Cleanup: gjør testen idempotent ift unique active constraint
        (
            db.query(Deviation)
            .filter(Deviation.rule_id == rule_row.id)
            .filter(Deviation.subject_key == subject_key)
            .filter(Deviation.org_id == "default")
            .filter(Deviation.home_id == "default")
            .filter(Deviation.subject_id == "default")
            .delete(synchronize_session=False)
        )
        db.commit()

        # Given: et aktivt OPEN avvik finnes
        dev = Deviation(
            rule_id=rule_row.id,
            status=DeviationStatus.OPEN,
            severity=2,
            started_at=now,
            last_seen_at=now,
            subject_key=subject_key,
            org_id="default",
            home_id="default",
            subject_id="default",
            context={
                "rule_key": rule_key,
                "title": "x",
                "explanation": "x",
                "window": {},
                "timestamp": now.isoformat(),
                "severity_str": "MEDIUM",
            },
            evidence={"event_ids": []},
        )
        db.add(dev)
        db.commit()
        db.refresh(dev)

        # When: bruker ACK'er avviket
        dev.status = DeviationStatus.ACK
        db.commit()
        db.refresh(dev)

        # Then: status er ACK (aktivt avvik)
        assert dev.status == DeviationStatus.ACK

        # When: stale-close skjer (modellert eksplisitt i test)
        dev.status = DeviationStatus.CLOSED
        db.commit()
        db.refresh(dev)

        # Then: avviket er CLOSED
        assert dev.status == DeviationStatus.CLOSED

        # When: regelen trigger igjen etter CLOSED (ny episode)
        now2 = utcnow()
        dev2 = Deviation(
            rule_id=rule_row.id,
            status=DeviationStatus.OPEN,
            severity=2,
            started_at=now2,
            last_seen_at=now2,
            subject_key=subject_key,
            org_id="default",
            home_id="default",
            subject_id="default",
            context={
                "rule_key": rule_key,
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

        # Then: vi har en ny OPEN rad i tillegg til den gamle CLOSED
        rows = (
            db.query(Deviation)
            .filter(Deviation.rule_id == rule_row.id)
            .filter(Deviation.subject_key == subject_key)
            .filter(Deviation.org_id == "default")
            .filter(Deviation.home_id == "default")
            .filter(Deviation.subject_id == "default")
            .order_by(Deviation.id.asc())
            .all()
        )
        assert len(rows) >= 2
        assert any(r.status == DeviationStatus.CLOSED for r in rows)
        assert any(r.status == DeviationStatus.OPEN for r in rows)

    finally:
        db.close()
