from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from config.rule_config import load_rule_config
from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window

RULE_ID = "R-003"


def _params() -> dict:
    cfg = load_rule_config()
    p = cfg.rule_params(RULE_ID)
    return p if isinstance(p, dict) else {}


def _followup_minutes() -> int:
    return int(_params().get("followup_minutes", 10))


def _door_category() -> str:
    return str(_params().get("door_category", "door"))


def _motion_categories() -> list[str]:
    """
    Prefer new param: motion_categories: ["motion","presence"]
    Back-compat: motion_category: "motion"
    Default: ["motion"]
    """
    p = _params()
    cats = p.get("motion_categories")
    if isinstance(cats, list) and cats:
        return [str(x) for x in cats]
    cat = p.get("motion_category")
    if isinstance(cat, str) and cat.strip():
        return [cat.strip()]
    return ["motion"]


def _payload_state_keys() -> list[str]:
    keys = _params().get("payload_state_keys", ["state", "value"])
    if isinstance(keys, list) and keys:
        return [str(x) for x in keys]
    return ["state", "value"]


def _door_name_keys() -> list[str]:
    keys = _params().get("door_name_keys", ["door", "name"])
    if isinstance(keys, list) and keys:
        return [str(x) for x in keys]
    return ["door", "name"]


def _required_door_name() -> str:
    return str(_params().get("required_door_name", "front"))


def _door_open_value() -> str:
    return str(_params().get("door_open_value", "open"))


def _motion_on_value() -> str:
    return str(_params().get("motion_on_value", "on"))


def _get_first(payload: object, keys: list[str]) -> str | None:
    if not isinstance(payload, dict):
        return None
    for k in keys:
        v = payload.get(k)
        if v is not None:
            return str(v)
    return None


def eval_r003_front_door_open_no_motion_after(
    session: Session, since: datetime, until: datetime, now: datetime
) -> List[DeviationV1]:
    follow_minutes = _followup_minutes()

    door_rows = (
        session.query(EventDB)
        .filter(EventDB.timestamp >= since)
        .filter(EventDB.timestamp < until)  # until eksklusiv
        .filter(EventDB.category == _door_category())
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    required_name = _required_door_name()
    door_open = _door_open_value()
    motion_on = _motion_on_value()
    motion_cats = _motion_categories()

    triggered = False
    evidence: List[str] = []

    for d in door_rows:
        state = _get_first(d.payload, _payload_state_keys())
        door_name = _get_first(d.payload, _door_name_keys())

        # Deterministisk match: configured door open
        if state != door_open or door_name != required_name:
            continue

        follow_until = d.timestamp + timedelta(minutes=follow_minutes)

        motion_rows = (
            session.query(EventDB)
            .filter(EventDB.timestamp >= d.timestamp)
            .filter(EventDB.timestamp < follow_until)  # follow_until eksklusiv
            .filter(EventDB.category.in_(motion_cats))
            .order_by(EventDB.timestamp.asc())
            .all()
        )

        has_motion_on = False
        for m in motion_rows:
            m_state = _get_first(m.payload, _payload_state_keys())
            # If motion/presence has explicit state/value, require it to be "on"
            if m_state is None:
                has_motion_on = True
                break
            if m_state == motion_on:
                has_motion_on = True
                break

        if not has_motion_on:
            triggered = True
            evidence.append(str(d.id))
            break

    if not triggered:
        return []

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=now,
            severity="MEDIUM",
            title="Mulig uvanlig hendelse etter dør",
            explanation=(
                f"Døren ble åpnet, men systemet registrerte ingen aktivitet i de neste {follow_minutes} minuttene. "
                "Det kan være at personen gikk ut, falt, eller at sensorer ikke registrerte aktivitet."
            ),
            evidence=evidence,
            window=Window(since=since, until=until),
        )
    ]
