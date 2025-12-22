from datetime import datetime
from typing import List
from sqlalchemy.orm import Session

from schemas.deviation_v1 import DeviationV1, Window
from models.db_event import EventDB

from util.time import to_db_utc_naive
RULE_ID = "R-001"

def eval_r001_no_motion(session: Session, since: datetime, until: datetime, now: datetime) -> List[DeviationV1]:
    since_db = to_db_utc_naive(since, "since")
    until_db = to_db_utc_naive(until, "until")

    rows = (
        session.query(EventDB)
        .filter(EventDB.timestamp >= since_db)
        .filter(EventDB.timestamp < until_db)
        .filter(EventDB.category == "motion")
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    if rows:
        return []

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=now,
            severity="MEDIUM",
            title="Ingen bevegelse registrert i valgt tidsvindu",
            explanation="Det finnes ingen motion-hendelser i vurdert tidsvindu. Sjekk sensor, dekning eller om personen har vært inaktiv/ute.",
            evidence=[],
            window=Window(since=since, until=until),
        )
    ]
