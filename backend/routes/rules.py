from __future__ import annotations

from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_db
from config.rule_config import load_rule_config
from models.rule import Rule
from models.rule import RuleType
from services.rules.registry import RULE_REGISTRY
from services.rules.gating import build_rule_truth

router = APIRouter(prefix="/rules", tags=["rules"])
logger = logging.getLogger("rules.routes")


_RULE_HUMAN_TEXT = {
    "R-001": {
        "display_name": "Lite eller ingen bevegelse i tidsvindu",
        "human_explanation": "Regelen følger med på om det er mye mindre bevegelse enn vanlig i et relevant tidsvindu.",
    },
    "R-002": {
        "display_name": "Ytterdør åpen om natten",
        "human_explanation": "Regelen varsler når ytterdør åpnes i nattperioden der det vanligvis forventes ro.",
    },
    "R-003": {
        "display_name": "Dør åpnet uten bevegelse etterpå",
        "human_explanation": "Regelen ser etter situasjoner der en dør åpnes, men det ikke kommer normal bevegelse i etterkant.",
    },
    "R-004": {
        "display_name": "Langt opphold på bad",
        "human_explanation": "Regelen markerer uvanlig lang aktivitet på bad sammenlignet med normal bruk.",
    },
    "R-005": {
        "display_name": "Lite baderomsaktivitet over tid",
        "human_explanation": "Regelen ser etter at baderomsaktivitet over et døgn faller tydelig under det som er vanlig.",
    },
    "R-006": {
        "display_name": "Lite stueaktivitet på dagtid",
        "human_explanation": "Regelen følger med på om stueaktivitet på dagtid blir klart lavere enn forventet.",
    },
    "R-007": {
        "display_name": "Nattvandring mellom rom",
        "human_explanation": "Regelen oppdager mange rombytter i nattperioden sammenlignet med normalt mønster.",
    },
    "R-008": {
        "display_name": "Mange dørhendelser på kort tid",
        "human_explanation": "Regelen markerer uvanlig tett serie med døråpning/lukking i samme tidsrom.",
    },
    "R-009": {
        "display_name": "Innsamling stoppet",
        "human_explanation": "Regelen varsler når systemet ikke mottar forventede liveness-hendelser innen rimelig tid.",
    },
    "R-010": {
        "display_name": "Sensor eller rom virker fastlåst",
        "human_explanation": "Regelen ser etter signaler som står urimelig lenge i samme tilstand uten normal variasjon.",
    },
}


def _human_rule_text(rule_id: str, spec_description: str | None) -> dict:
    fallback = (spec_description or rule_id or "").strip() or "Ukjent regel"
    info = _RULE_HUMAN_TEXT.get(rule_id, {})
    return {
        "display_name": info.get("display_name") or fallback,
        "human_explanation": info.get("human_explanation") or fallback,
    }


def _resolve_scope(db: Session) -> tuple[str, str, str]:
    """
    Best-effort scope resolver for evaluation-truth endpoint.

    CI/fresh installs may not have optional tables like "subjects" yet.
    Never raise here; fall back to default scope.
    """
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT org_id, home_id, subject_id
                    FROM subjects
                    ORDER BY created_at ASC NULLS LAST
                    LIMIT 1
                    """
                )
            )
            .mappings()
            .first()
        )
    except Exception:
        logger.warning("rules_scope_resolution_failed_falling_back_default", exc_info=True)
        return ("default", "default", "default")

    if row:
        return (
            str(row.get("org_id") or "default"),
            str(row.get("home_id") or "default"),
            str(row.get("subject_id") or "default"),
        )
    return ("default", "default", "default")



def _severity_label(score: int) -> str:
    return {1: "LOW", 2: "MEDIUM", 3: "HIGH"}.get(int(score or 2), "MEDIUM")



def _evaluation_truth_config(yaml_rule: dict) -> dict:
    return {
        "evaluation_mode": yaml_rule.get("evaluation_mode", "independent"),
        "requires_baseline": bool(yaml_rule.get("requires_baseline", False)),
        "requires_profile": bool(yaml_rule.get("requires_profile", False)),
        "profile_mode": yaml_rule.get("profile_mode"),
        "uses_default_profile_when_missing": bool(
            yaml_rule.get("uses_default_profile_when_missing", False)
        ),
        "min_days_with_data": yaml_rule.get("min_days_with_data"),
    }

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
        "evaluation_truth_config": _evaluation_truth_config(yaml_rule),
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


@router.get("/evaluation-truth")
def get_rules_evaluation_truth(db: Session = Depends(get_db)):
    cfg = load_rule_config()
    yaml_rules = (cfg.raw.get("rules", {}) if isinstance(cfg.raw, dict) else {}) or {}
    org_id, home_id, subject_id = _resolve_scope(db)

    rows = []
    for rid in sorted(yaml_rules.keys()):
        if not cfg.rule_enabled_in_scheduler(rid):
            continue
        truth = build_rule_truth(
            cfg,
            rid,
            db=db,
            org_id=org_id,
            home_id=home_id,
            subject_id=subject_id,
        )
        rows.append({"rule_id": rid, **truth})

    return {
        "scope": {"org_id": org_id, "home_id": home_id, "subject_id": subject_id},
        "rules": rows,
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
    org_id, home_id, subject_id = _resolve_scope(db)
    truth_by_rule = {}
    for name in sorted(yaml_rules.keys()):
        y = dict(yaml_rules.get(name) or {})
        spec = RULE_REGISTRY.get(name)
        human = _human_rule_text(name, spec.description if spec is not None else name)
        enabled_in_scheduler = bool(y.get("enabled_in_scheduler", False))
        lookback_minutes = y.get("lookback_minutes")
        expire_after_minutes = y.get("expire_after_minutes")
        params = dict(y.get("params", {}) or {})

        r = by_name.get(name)
        if enabled_in_scheduler:
            try:
                truth_by_rule[name] = build_rule_truth(
                    cfg,
                    name,
                    db=db,
                    org_id=org_id,
                    home_id=home_id,
                    subject_id=subject_id,
                )
            except Exception:
                logger.warning("rules_list_truth_build_failed", extra={"rule_id": name}, exc_info=True)
        out.append(
            {
                "name": name,
                "rule_id": name,
                "display_name": human["display_name"],
                "human_explanation": human["human_explanation"],
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
                "evaluation_truth_config": _evaluation_truth_config(y),
                "runtime_status": truth_by_rule.get(name),
            }
        )

    # Include DB-only rules too (if any exist that are not in YAML)
    for name, r in sorted(by_name.items()):
        if name in yaml_rules:
            continue
        spec = RULE_REGISTRY.get(name)
        human = _human_rule_text(name, spec.description if spec is not None else name)
        out.append(
            {
                "name": name,
                "rule_id": name,
                "display_name": human["display_name"],
                "human_explanation": human["human_explanation"],
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
                "evaluation_truth_config": _evaluation_truth_config({}),
                "runtime_status": None,
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
