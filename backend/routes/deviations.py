# backend/routes/deviations.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List

from models.deviation import Deviation, DeviationStatus
from db import get_db

from services.rule_engine import evaluate_rules

from schemas.deviation_v1 import DeviationV1
router = APIRouter(prefix="/deviations", tags=["deviations"])


@router.get("")
def list_deviations(db: Session = Depends(get_db)):
    return (
        db.query(Deviation)
        .order_by(Deviation.severity.desc(), Deviation.last_seen_at.desc())
        .all()
    )



@router.patch("/{deviation_id}")
def patch_deviation(deviation_id: int, payload: dict, db: Session = Depends(get_db)):
    dev = db.get(Deviation, deviation_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Deviation not found")

    if "status" in payload:
        try:
            dev.status = DeviationStatus(payload["status"])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid status")

    db.commit()
    db.refresh(dev)
    return dev


#
# --- Thin-slice, beregnede avvik (Avvik v1) ---
#
@router.get("/evaluate", response_model=List[DeviationV1])
def evaluate_deviations(
    since: datetime = Query(..., description="ISO 8601"),
    until: datetime = Query(..., description="ISO 8601"),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    devs = evaluate_rules(db, since=since, until=until, now=now)

    return devs
