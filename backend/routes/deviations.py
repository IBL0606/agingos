# backend/routes/deviations.py

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from models.deviation_v1_db import DeviationV1DB, DeviationV1Status
from schemas.deviation_v1 import DeviationV1
from services.deviation_store_v1 import upsert_deviations_v1, close_stale_deviations_v1
from services.rules.r001 import eval_r001_no_motion
from services.rules.r002 import eval_r002_front_door_open_at_night
from services.rules.r003 import eval_r003_front_door_open_no_motion_after

router = APIRouter(prefix="/deviations", tags=["deviations"])

DEFAULT_EXPIRE_AFTER_MINUTES = 60
RULE_IDS = ["R-001", "R-002", "R-003"]


def _compute_deviations(db: Session, since: datetime, until: datetime) -> List[DeviationV1]:
    """
    Shared helper for both /evaluate and /persist.
    """
    now = datetime.now(timezone.utc)

    devs: List[DeviationV1] = []
    devs += eval_r001_no_motion(db, since=since, until=until, now=now)
    devs += eval_r002_front_door_open_at_night(db, since=since, until=until, now=now)
    devs += eval_r003_front_door_open_no_motion_after(db, since=since, until=until, now=now)
    return devs


@router.get("")
def list_deviations(
    status: str = Query(default="OPEN"),
    subject_key: str = Query(default="default"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    try:
        st = DeviationV1Status(status)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid status")

    rows = (
        db.query(DeviationV1DB)
        .filter(DeviationV1DB.subject_key == subject_key)
        .filter(DeviationV1DB.status == st)
        .order_by(DeviationV1DB.last_seen_at.desc())
        .limit(limit)
        .all()
    )

    # Returner Avvik v1 + ekstra felter for “menneskelig visning”
    return [
        {
            "deviation_id": r.deviation_id,
            "rule_id": r.rule_id,
            "timestamp": r.updated_at,
            "severity": r.severity,
            "title": r.title,
            "explanation": r.explanation,
            "evidence": r.evidence,
            "window": {"since": r.window_since, "until": r.window_until},
            "status": r.status.value,
            "subject_key": r.subject_key,
            "first_seen_at": r.first_seen_at,
            "last_seen_at": r.last_seen_at,
        }
        for r in rows
    ]


@router.patch("/{deviation_id}")
def patch_deviation(deviation_id: str, payload: dict, db: Session = Depends(get_db)):
    dev = db.query(DeviationV1DB).filter(DeviationV1DB.deviation_id == deviation_id).one_or_none()
    if not dev:
        raise HTTPException(status_code=404, detail="Deviation not found")

    if "status" in payload:
        try:
            dev.status = DeviationV1Status(payload["status"])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid status")

        if dev.status == DeviationV1Status.CLOSED:
            dev.closed_at = datetime.utcnow()
        else:
            dev.closed_at = None

    dev.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(dev)

    return {
        "deviation_id": dev.deviation_id,
        "rule_id": dev.rule_id,
        "status": dev.status.value,
        "subject_key": dev.subject_key,
        "last_seen_at": dev.last_seen_at,
        "updated_at": dev.updated_at,
    }


#
# --- Thin-slice, beregnede avvik (Avvik v1) ---
#
@router.get("/evaluate", response_model=List[DeviationV1])
def evaluate_deviations(
    since: datetime = Query(..., description="ISO 8601"),
    until: datetime = Query(..., description="ISO 8601"),
    db: Session = Depends(get_db),
):
    return _compute_deviations(db=db, since=since, until=until)


@router.post("/persist")
def persist_deviations(
    since: datetime = Query(..., description="ISO 8601"),
    until: datetime = Query(..., description="ISO 8601"),
    subject_key: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    # DB-kolonnene er timestamp without time zone, så vi bruker utcnow() (naiv) for lagring.
    now_db = datetime.utcnow()

    devs = _compute_deviations(db=db, since=since, until=until)

    result, seen_keys = upsert_deviations_v1(
        db=db,
        deviations=devs,
        subject_key=subject_key,
        now=now_db,
    )

    closed = close_stale_deviations_v1(
        db=db,
        subject_key=subject_key,
        rule_ids=RULE_IDS,
        seen_keys=seen_keys,
        now=now_db,
        expire_after_minutes=DEFAULT_EXPIRE_AFTER_MINUTES,
    )

    db.commit()
    return {"created": result.created, "updated": result.updated, "reopened": result.reopened, "closed": closed}
