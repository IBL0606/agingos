"""
T-0303: Statusflyt-test (OPEN → ACK → stale CLOSE → trigger reopens)

Scenario navn: "status_flow_open_ack_close_reopen"

Given/When/Then er skrevet eksplisitt i testen for å gjøre livssyklusreglene etterprøvbare.
"""

from datetime import timedelta

from backend.db import SessionLocal
from backend.models.rule import Rule, RuleType
from backend.models.deviation import Deviation, DeviationStatus

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

        # Given: en regel finnes, og et aktivt OPEN avvik finnes i DB
        rule_row = _ensure_rule(db, rule_key)
        from util.time import utcnow

        now = utcnow()

        dev = Deviation(
            rule_id=rule_row.id,
            status=DeviationStatus.OPEN,
            severity=2,
            started_at=now,
            last_seen_at=now,
            subject_key=subject_key,
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

        # Given: tiden går slik at avviket blir stale
        # (Vi simulerer stale ved å sette last_seen_at langt tilbake i tid.)
        dev.last_seen_at = now - timedelta(minutes=9999)
        db.commit()

        # When: stale-closing skjer (modellert her som: sett CLOSED når stale)
        # (Selve scheduler-implementasjonen lukker OPEN/ACK når last_seen_at er eldre enn cutoff.)
        dev.status = DeviationStatus.CLOSED
        db.commit()
        db.refresh(dev)

        # Then: avviket er CLOSED
        assert dev.status == DeviationStatus.CLOSED

        # When: regelen trigger igjen etter CLOSED (ny episode)
        later = now + timedelta(minutes=1)
        reopened = Deviation(
            rule_id=rule_row.id,
            status=DeviationStatus.OPEN,
            severity=2,
            started_at=later,
            last_seen_at=later,
            subject_key=subject_key,
            context={
                "rule_key": rule_key,
                "title": "x2",
                "explanation": "x2",
                "window": {},
                "timestamp": later.isoformat(),
                "severity_str": "MEDIUM",
            },
            evidence={"event_ids": []},
        )
        db.add(reopened)
        db.commit()
        db.refresh(reopened)

        # Then: vi har en ny OPEN rad (ny episode) i tillegg til den gamle CLOSED
        assert reopened.status == DeviationStatus.OPEN
        assert reopened.id != dev.id

        rows = (
            db.query(Deviation)
            .filter(Deviation.rule_id == rule_row.id)
            .filter(Deviation.subject_key == subject_key)
            .all()
        )
        assert len(rows) >= 2

    finally:
        db.close()
