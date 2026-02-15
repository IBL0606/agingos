from datetime import datetime, time
from typing import List

from sqlalchemy.orm import Session

from config.rule_config import load_rule_config
from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window

RULE_ID = "R-002"


def _params() -> dict:
    cfg = load_rule_config()
    params = cfg.rule_params(RULE_ID)
    return params if isinstance(params, dict) else {}


def _category() -> str:
    p = _params()
    v = p.get("category")
    return str(v).strip() if isinstance(v, str) and v.strip() else "door"


def _payload_state_keys() -> list[str]:
    p = _params()
    keys = p.get("payload_state_keys")
    if isinstance(keys, list) and keys:
        return [str(x) for x in keys]
    return ["state", "value"]


def _trigger_value() -> str:
    p = _params()
    v = p.get("trigger_value")
    return str(v).strip() if isinstance(v, str) and v.strip() else "open"


def _night_window() -> tuple[time, time]:
    """
    Reads night window from config:
      rules.R-002.params.night_window.start_local_time
      rules.R-002.params.night_window.end_local_time

    Defaults: 23:00:00 -> 06:00:00
    """
    p = _params()
    w = p.get("night_window", {}) if isinstance(p, dict) else {}
    if not isinstance(w, dict):
        w = {}
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


def _event_state(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    for k in _payload_state_keys():
        if k in payload:
            v = payload.get(k)
            return None if v is None else str(v)
    return None


def eval_r002_front_door_open_at_night(
    session: Session, since: datetime, until: datetime, now: datetime
) -> List[DeviationV1]:
    cat = _category()
    tv = _trigger_value()

    rows = (
        session.query(EventDB)
        .filter(EventDB.timestamp >= since)
        .filter(EventDB.timestamp < until)  # until eksklusiv
        .filter(EventDB.category == cat)
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    evidence: List[str] = []
    for r in rows:
        state = _event_state(r.payload)
        if state == tv and _is_night(r.timestamp):
            evidence.append(str(r.id))

    if not evidence:
        return []

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=now,
            severity="HIGH",
            title="Ytterdør åpnet på natt",
            explanation="Det er registrert at ytterdør ble åpnet i nattetid. Sjekk om dette var forventet.",
            evidence=evidence,
            window=Window(since=since, until=until),
        )
    ]
