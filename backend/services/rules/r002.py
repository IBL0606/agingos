from datetime import datetime, time
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from schemas.deviation_v1 import DeviationV1, Window
from models.db_event import EventDB

RULE_ID = "R-002"

# Natt: 23:00 -> 06:00 (går over midnatt)
NIGHT_START = time(23, 0, 0)
NIGHT_END = time(6, 0, 0)


def _is_night(ts: datetime) -> bool:
    t = ts.time()
    return (t >= NIGHT_START) or (t < NIGHT_END)


def eval_r002_front_door_open_at_night(
    session: Session, since: datetime, until: datetime, now: datetime
) -> List[DeviationV1]:
    rows = (
        session.query(EventDB)
        .filter(EventDB.timestamp >= since)
        .filter(EventDB.timestamp < until)  # until eksklusiv
        .filter(EventDB.category == "door")
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    triggered = False
    evidence: List[UUID] = []

    for r in rows:
        state = None
        if isinstance(r.payload, dict):
            state = r.payload.get("state") or r.payload.get("value")

        if state == "open" and _is_night(r.timestamp):
            triggered = True
            # Evidence er "best effort": hvis r.id ikke er UUID, lar vi evidence være tom
            try:
                evidence.append(UUID(str(r.id)))
            except Exception:
                pass

    if not triggered:
        return []

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=now,
            severity="HIGH",
            title="Ytterdør åpnet på natt",
            explanation="Det er registrert at ytterdør ble åpnet i nattetid. Sjekk om dette var forventet.",
            evidence=evidence,  # kan være tom
            window=Window(since=since, until=until),
        )
    ]
