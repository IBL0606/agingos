from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from models.rule import Rule
from models.rule import RuleType

router = APIRouter(prefix="/rules", tags=["rules"])


def _utc_now_iso() -> str:
    # RFC3339-ish with Z, seconds precision (stable for UI)
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _apply_proposal_timestamps(params: dict) -> dict:
    """
    Persist proposal lifecycle timestamps server-side.
    - Set *once* (idempotent): only if missing.
    - Overwrite placeholders for activated_at when activating.
    """
    if not isinstance(params, dict):
        return {}

    p = dict(params)
    now = _utc_now_iso()

    act = p.get("proposal_action")
    status = p.get("proposal_status")

    if act == "test_7_days" or status == "testing":
        p.setdefault("proposal_test_started_at", now)


    if act == "reject" or status == "rejected":
        p.setdefault("proposal_rejected_at", now)

    if act == "activate" or status == "active":
        cur = p.get("proposal_activated_at")
        # Overwrite placeholders/invalid values, but keep real timestamps idempotent
        if not cur or str(cur).strip() in ("__SERVER__", "server", "now", "AUTO"):
            p["proposal_activated_at"] = now

    return p


@router.get("")
def list_rules(db: Session = Depends(get_db)):
    return db.query(Rule).order_by(Rule.id.desc()).all()


@router.post("")
def create_rule(payload: dict, db: Session = Depends(get_db)):
    if "name" not in payload or "rule_type" not in payload:
        raise HTTPException(status_code=400, detail="name and rule_type are required")

    try:
        rule_type = RuleType(payload["rule_type"])
    except Exception:
        raise HTTPException(status_code=400, detail="invalid rule_type")

    incoming_params = _apply_proposal_timestamps(payload.get("params", {}) or {})

    # Upsert by name (idempotent)
    existing = db.query(Rule).filter(Rule.name == payload["name"]).first()
    if existing:
        # Merge params (new wins), but keep timestamps idempotent (setdefault in helper)
        merged = dict(existing.params or {})
        merged.update(incoming_params)
        merged = _apply_proposal_timestamps(merged)

        existing.rule_type = rule_type
        existing.params = merged
        existing.severity = payload.get("severity", existing.severity)
        existing.is_enabled = payload.get("is_enabled", existing.is_enabled)

        db.commit()
        db.refresh(existing)
        return existing

    rule = Rule(
        name=payload["name"],
        rule_type=rule_type,
        params=incoming_params,
        severity=payload.get("severity", 2),
        is_enabled=payload.get("is_enabled", True),
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/{rule_id}")
def patch_rule(rule_id: int, payload: dict, db: Session = Depends(get_db)):
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if "name" in payload:
        rule.name = payload["name"]
    if "severity" in payload:
        rule.severity = payload["severity"]
    if "is_enabled" in payload:
        rule.is_enabled = payload["is_enabled"]

    if "params" in payload:
        merged = dict(rule.params or {})
        merged.update(payload["params"] or {})
        merged = _apply_proposal_timestamps(merged)
        rule.params = merged

    db.commit()
    db.refresh(rule)
    return rule
