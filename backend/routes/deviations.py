# backend/routes/deviations.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from models.deviation import Deviation, DeviationStatus
from db import get_db

from services.rule_engine import evaluate_rules

from schemas.deviation_v1 import DeviationV1
from util.time import require_utc_aware, utcnow

router = APIRouter(prefix="/deviations", tags=["deviations"])


from fastapi import Query  # hvis ikke allerede importert
from typing import List

from models.deviation import Deviation, DeviationStatus  # sørg for at DeviationStatus finnes her
from schemas.deviation_persisted import DeviationPersisted  # filen du sa er ferdig

def _severity_str_from_score(score: int) -> str:
    return {1: "LOW", 2: "MEDIUM", 3: "HIGH"}.get(int(score or 2), "MEDIUM")

def _serialize_persisted(dev: Deviation) -> dict:
    ctx = dev.context or {}
    window = (ctx.get("window") or {})

    evidence_ids = (dev.evidence or {}).get("event_ids", []) or []

    rule_key = ctx.get("rule_key")
    severity_str = ctx.get("severity_str") or _severity_str_from_score(dev.severity)
    title = ctx.get("title") or ""
    explanation = ctx.get("explanation") or ""
    timestamp = ctx.get("timestamp") or dev.last_seen_at

    return {
        "deviation_id": dev.id,
        "rule_id": rule_key or str(dev.rule_id),
        "status": dev.status.value if hasattr(dev.status, "value") else str(dev.status),
        "severity": severity_str,
        "title": title,
        "explanation": explanation,
        "timestamp": timestamp,
        "started_at": dev.started_at,
        "last_seen_at": dev.last_seen_at,
        "subject_key": dev.subject_key,
        "evidence": evidence_ids,
        "window": {
            "since": window.get("since"),
            "until": window.get("until"),
        },
    }

@router.get("", response_model=List[DeviationPersisted])
def list_deviations(
    status: DeviationStatus | None = Query(None),
    subject_key: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Deviation)

    if status is not None:
        q = q.filter(Deviation.status == status)

    if subject_key is not None:
        q = q.filter(Deviation.subject_key == subject_key)

    devs = (
        q.order_by(Deviation.severity.desc(), Deviation.last_seen_at.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_persisted(d) for d in devs]


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
    try:
        since = require_utc_aware(since, "since")
        until = require_utc_aware(until, "until")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    now = utcnow()

    devs = evaluate_rules(db, since=since, until=until, now=now)

    return devs
