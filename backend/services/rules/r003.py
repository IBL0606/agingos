from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from config.rule_config import load_rule_config
from models.db_event import EventDB
from util.time import to_db_utc_naive
from schemas.deviation_v1 import DeviationV1, Window

RULE_ID = "R-003"


def _followup_minutes() -> int:
    """
    Reads follow-up window from config:
      rules.R-003.params.followup_minutes

    Falls back to sim-baseline default (10).
    """
    cfg = load_rule_config()
    params = cfg.rule_params(RULE_ID)
    if isinstance(params, dict):
        return int(params.get("followup_minutes", 10))
    return 10


def eval_r003_front_door_open_no_motion_after(
    session: Session, since: datetime, until: datetime, now: datetime
) -> List[DeviationV1]:
    since_db = to_db_utc_naive(since, "since")
    until_db = to_db_utc_naive(until, "until")
    follow_minutes = _followup_minutes()

    # Finn dør-events i evalueringsvinduet
    door_rows = (
        session.query(EventDB)
        .filter(EventDB.timestamp >= since_db)
        .filter(EventDB.timestamp < until_db)  # until eksklusiv
        .filter(EventDB.category == "door")
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    triggered = False
    evidence: List[UUID] = []

    for d in door_rows:
        state = None
        door_name = None
        if isinstance(d.payload, dict):
            state = d.payload.get("state") or d.payload.get("value")
            door_name = d.payload.get("door") or d.payload.get("name")

        # Deterministisk match: front door open
        if state != "open" or door_name != "front":
            continue

        follow_until = d.timestamp + timedelta(minutes=follow_minutes)

        # Finn motion-events i de neste N minuttene etter dør-eventet
        motion_rows = (
            session.query(EventDB)
            .filter(EventDB.timestamp >= d.timestamp)
            .filter(EventDB.timestamp < follow_until)  # follow_until eksklusiv
            .filter(EventDB.category == "motion")
            .order_by(EventDB.timestamp.asc())
            .all()
        )

        has_motion_on = False
        for m in motion_rows:
            m_state = None
            if isinstance(m.payload, dict):
                m_state = m.payload.get("state") or m.payload.get("value")
            if m_state == "on":
                has_motion_on = True
                break

        if not has_motion_on:
            triggered = True
            # Evidence: dør-eventet som utløste regelen (best effort)
            try:
                evidence.append(UUID(str(d.id)))
            except Exception:
                pass
            # Samme mønster som R-002: én deviation hvis regelen trigges
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
                f"Døren ble åpnet, men systemet registrerte ingen bevegelse i de neste {follow_minutes} minuttene. "
                    "Det kan være at personen gikk ut, falt, eller at sensorer ikke registrerte aktivitet."
            ),
            evidence=evidence,  # kan være tom
            window=Window(since=since, until=until),
        )
    ]
