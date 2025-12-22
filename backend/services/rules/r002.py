from datetime import datetime, time
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from config.rule_config import load_rule_config
from models.db_event import EventDB
from util.time import to_db_utc_naive
from schemas.deviation_v1 import DeviationV1, Window

RULE_ID = "R-002"


def _night_window() -> tuple[time, time]:
    """
    Reads night window from config:
      rules.R-002.params.night_window.start_local_time
      rules.R-002.params.night_window.end_local_time

    Falls back to sim-baseline defaults (23:00:00 -> 06:00:00).
    """
    cfg = load_rule_config()
    params = cfg.rule_params(RULE_ID)

    w = params.get("night_window", {}) if isinstance(params, dict) else {}
    start_s = w.get("start_local_time", "23:00:00")
    end_s = w.get("end_local_time", "06:00:00")

    return time.fromisoformat(start_s), time.fromisoformat(end_s)


def _is_night(ts: datetime) -> bool:
    start_t, end_t = _night_window()
    t = ts.time()

    # If the window crosses midnight (e.g. 23:00 -> 06:00)
    if start_t > end_t:
        return (t >= start_t) or (t < end_t)

    # Normal same-day window
    return start_t <= t < end_t


def eval_r002_front_door_open_at_night(
    session: Session, since: datetime, until: datetime, now: datetime
) -> List[DeviationV1]:
    since_db = to_db_utc_naive(since, "since")
    until_db = to_db_utc_naive(until, "until")
    rows = (
        session.query(EventDB)
        .filter(EventDB.timestamp >= since_db)
        .filter(EventDB.timestamp < until_db)  # until eksklusiv
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
