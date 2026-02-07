# backend/routes/deviations.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from models.deviation import Deviation, DeviationStatus
from db import get_db

from services.rule_engine import evaluate_rules

from schemas.deviation_v1 import DeviationV1
from schemas.deviation_persisted import DeviationPersisted
from util.time import require_utc_aware, utcnow

router = APIRouter(prefix="/deviations", tags=["deviations"])


def _severity_str_from_score(score: int) -> str:
    return {1: "LOW", 2: "MEDIUM", 3: "HIGH"}.get(int(score or 2), "MEDIUM")


def _serialize_persisted(dev):
    """Serialize persisted deviation to API schema (DeviationPersisted).

    Keep legacy fields (title/explanation/timestamp/window/severity as str),
    but return evidence as-is to preserve e.g. _monitor_mode.
    """

    def g(*names, default=None):
        for n in names:
            if hasattr(dev, n):
                return getattr(dev, n)
        return default

    ctx = g("context", default=None) or {}
    window = (ctx.get("window") or {}) if isinstance(ctx, dict) else {}

    evidence_obj = g("evidence", default=None)
    evidence_event_ids = []
    if isinstance(evidence_obj, dict):
        ev = evidence_obj.get("event_ids", [])
        if isinstance(ev, list):
            evidence_event_ids = ev
    elif isinstance(evidence_obj, list):
        evidence_event_ids = evidence_obj

    # status enum -> str
    status_val = g("status", default=None)
    if hasattr(status_val, "value"):
        status_val = status_val.value
    else:
        status_val = str(status_val) if status_val is not None else "OPEN"

    # severity (stored as int score) -> "LOW/MEDIUM/HIGH"
    sev_score = g("severity", default=None)
    severity_str = ctx.get("severity_str") if isinstance(ctx, dict) else None
    if not severity_str:
        severity_str = _severity_str_from_score(int(sev_score or 2))

    # rule id string (prefer ctx.rule_key like "R-001", else dev.rule_id)
    rule_id = ctx.get("rule_key") if isinstance(ctx, dict) else None
    if not rule_id:
        rule_id = g("rule_id", default=None)
    rule_id = str(rule_id) if rule_id is not None else ""

    title = (ctx.get("title") if isinstance(ctx, dict) else None) or ""
    explanation = (ctx.get("explanation") if isinstance(ctx, dict) else None) or ""

    # timestamp: prefer ctx.timestamp else last_seen_at
    timestamp = (ctx.get("timestamp") if isinstance(ctx, dict) else None) or g("last_seen_at", default=None)

    return {
        "deviation_id": g("deviation_id", "id"),
        "rule_id": rule_id,
        "status": status_val,
        "severity": severity_str,
        "title": title,
        "explanation": explanation,
        "timestamp": timestamp,
        "started_at": g("started_at", default=None),
        "last_seen_at": g("last_seen_at", default=None),
        "subject_key": g("subject_key", default="default") or "default",
        "evidence": evidence_obj,
        "evidence_event_ids": evidence_event_ids,
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


@router.patch("/{deviation_id}", response_model=DeviationPersisted)
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
    return _serialize_persisted(dev)


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
