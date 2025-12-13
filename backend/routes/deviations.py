from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from models.deviation import Deviation
from db import get_db

router = APIRouter(prefix="/deviations", tags=["deviations"])

@router.get("")
def list_deviations(db: Session = Depends(get_db)):
    return (
        db.query(Deviation)
        .order_by(Deviation.last_seen_at.desc())
        .all()
    )

from fastapi import HTTPException
from models.deviation import DeviationStatus

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
