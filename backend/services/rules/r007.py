from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from schemas.deviation_v1 import DeviationV1


def eval_r007_todo(
    db: Session, *, since: datetime, until: datetime, now: datetime
) -> list[DeviationV1]:
    """TODO R-007: implement rule logic.

    Contract:
      - Deterministic given (db, since, until, now)
      - Must NOT write to DB (read-only)
      - Return [] if no deviation
    """
    return []
