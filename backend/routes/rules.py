from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from models.rule import Rule
from db import get_db

router = APIRouter(prefix="/rules", tags=["rules"])

@router.get("")
def list_rules(db: Session = Depends(get_db)):
    return db.query(Rule).order_by(Rule.id.desc()).all()

from fastapi import HTTPException
from models.rule import RuleType

@router.post("")
def create_rule(payload: dict, db: Session = Depends(get_db)):
    if "name" not in payload or "rule_type" not in payload:
        raise HTTPException(status_code=400, detail="name and rule_type are required")

    try:
        rule_type = RuleType(payload["rule_type"])
    except Exception:
        raise HTTPException(status_code=400, detail="invalid rule_type")

    rule = Rule(
        name=payload["name"],
        rule_type=rule_type,
        params=payload.get("params", {}),
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
    if "params" in payload:
        rule.params = payload["params"]
    if "severity" in payload:
        rule.severity = payload["severity"]
    if "is_enabled" in payload:
        rule.is_enabled = payload["is_enabled"]

    db.commit()
    db.refresh(rule)
    return rule
