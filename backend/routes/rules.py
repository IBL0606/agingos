from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from config.rule_config import load_rule_config
from models.rule import Rule
from models.rule import RuleType
from services.rules.registry import RULE_REGISTRY

router = APIRouter(prefix="/rules", tags=["rules"])


def _severity_label(score: int) -> str:
    return {1: "LOW", 2: "MEDIUM", 3: "HIGH"}.get(int(score or 2), "MEDIUM")


def _pilot_pack_row(rule_id: str, db_rule: Rule | None, yaml_rule: dict) -> dict:
    spec = RULE_REGISTRY.get(rule_id)
    severity_score = int(getattr(db_rule, "severity", 2) or 2)
    return {
        "rule_id": rule_id,
        "name": (spec.description if spec is not None else "NO_EVIDENCE"),
        "description": (
            spec.description
            if spec is not None
            else "NO_EVIDENCE: missing RuleSpec in RULE_REGISTRY"
        ),
        "severity": {
            "score": severity_score,
            "label": _severity_label(severity_score),
            "source": "rules.severity" if db_rule is not None else "default=2",
        },
        "scheduler_enabled": bool(yaml_rule.get("enabled_in_scheduler", False)),
        "cooldown_grouping": {
            "cooldown": "NONE",
            "grouping": "OPEN/ACK dedupe by rule+subject+scope in scheduler upsert",
            "evidence": [
                "services.scheduler._upsert_open_deviation filters existing OPEN/ACK by rule_id + subject_key + org/home/subject",
                "models.deviation unique partial index enforces one active row per rule_id + subject_key for OPEN/ACK",
            ],
        },
    }


@router.get("/pilot-pack")
def get_pilot_pack(db: Session = Depends(get_db)):
    """
    MUST-4 explicit pilot alarm rule pack for R-001..R-010.

    Truth policy:
    - cooldown is reported as NONE because no rule cooldown field exists in rules.yaml.
    - grouping reports only proven scheduler/deviation active-dedupe behavior.
    """
    cfg = load_rule_config()
    yaml_rules = (cfg.raw.get("rules", {}) if isinstance(cfg.raw, dict) else {}) or {}
    db_rows = db.query(Rule).all()
    by_name = {r.name: r for r in db_rows if getattr(r, "name", None)}

    out = []
    for rule_id in sorted(yaml_rules.keys()):
        out.append(
            _pilot_pack_row(
                rule_id,
                by_name.get(rule_id),
                dict(yaml_rules[rule_id] or {}),
            )
        )

    return {
        "pack": "MUST-4-pilot-alarm-rules",
        "rules": out,
        "notes": [
            "cooldown is NONE for all rules (no cooldown setting in backend/config/rules.yaml)",
            "grouping reflects scheduler/deviation active dedupe only; notification anti-spam is handled in outbox worker",
        ],
    }


def _utc_now_iso() -> str:
    # RFC3339-ish with Z, seconds precision (stable for UI)
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


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
    # YAML is source of truth for which rules exist / are scheduler-enabled.
    cfg = load_rule_config()
    yaml_rules = (cfg.raw.get("rules", {}) if isinstance(cfg.raw, dict) else {}) or {}

    # DB holds metadata (id/created_at/severity/is_enabled/params used elsewhere).
    db_rows = db.query(Rule).all()
    by_name = {r.name: r for r in db_rows if getattr(r, "name", None)}

    out = []
    for name in sorted(yaml_rules.keys()):
        y = dict(yaml_rules.get(name) or {})
        enabled_in_scheduler = bool(y.get("enabled_in_scheduler", False))
        lookback_minutes = y.get("lookback_minutes")
        expire_after_minutes = y.get("expire_after_minutes")
        params = dict(y.get("params", {}) or {})

        r = by_name.get(name)
        out.append(
            {
                "name": name,
                "enabled_in_scheduler": enabled_in_scheduler,
                "lookback_minutes": lookback_minutes,
                "expire_after_minutes": expire_after_minutes,
                "params": (r.params if r is not None else params) or {},
                "severity": (r.severity if r is not None else 2),
                "is_enabled": (r.is_enabled if r is not None else True),
                "id": (r.id if r is not None else None),
                "created_at": (
                    r.created_at.isoformat()
                    if (r is not None and r.created_at is not None)
                    else None
                ),
                "rule_type": (str(r.rule_type) if r is not None else None),
            }
        )

    # Include DB-only rules too (if any exist that are not in YAML)
    for name, r in sorted(by_name.items()):
        if name in yaml_rules:
            continue
        out.append(
            {
                "name": name,
                "enabled_in_scheduler": False,
                "lookback_minutes": None,
                "expire_after_minutes": None,
                "params": r.params or {},
                "severity": r.severity,
                "is_enabled": r.is_enabled,
                "id": r.id,
                "created_at": (
                    r.created_at.isoformat() if r.created_at is not None else None
                ),
                "rule_type": str(r.rule_type),
                "note": "db_only",
            }
        )

    return out


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
