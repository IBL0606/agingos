from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from config.rule_config import RuleConfig


def _safe_ratio(num: int | None, den: int | None) -> float | None:
    if den is None or den <= 0:
        return None
    if num is None:
        return None
    return float(num) / float(den)


def load_baseline_truth(
    db: Session,
    *,
    org_id: str,
    home_id: str,
    subject_id: str,
) -> dict[str, Any]:
    row = (
        db.execute(
            text(
                """
                SELECT
                  baseline_ready,
                  min_days_required,
                  days_with_data,
                  room_bucket_rows,
                  room_bucket_supported,
                  transition_rows,
                  transition_supported
                FROM baseline_model_status
                WHERE org_id = :org_id AND home_id = :home_id AND subject_id = :subject_id
                ORDER BY computed_at DESC
                LIMIT 1
                """
            ),
            {
                "org_id": org_id,
                "home_id": home_id,
                "subject_id": subject_id,
            },
        )
        .mappings()
        .first()
    )
    if not row:
        return {
            "baseline_ready": False,
            "min_days_required": None,
            "days_with_data": 0,
            "coverage_room_bucket": None,
            "coverage_transition": None,
            "has_status": False,
        }

    days = row.get("days_with_data")
    min_days = row.get("min_days_required")
    room_supported = row.get("room_bucket_supported")
    room_rows = row.get("room_bucket_rows")
    trans_supported = row.get("transition_supported")
    trans_rows = row.get("transition_rows")

    return {
        "baseline_ready": bool(row.get("baseline_ready")),
        "min_days_required": min_days,
        "days_with_data": int(days or 0),
        "coverage_room_bucket": _safe_ratio(int(room_supported or 0), int(room_rows or 0)),
        "coverage_transition": _safe_ratio(int(trans_supported or 0), int(trans_rows or 0)),
        "has_status": True,
    }


def build_rule_truth(
    cfg: RuleConfig,
    rule_id: str,
    *,
    db: Session,
    org_id: str,
    home_id: str,
    subject_id: str,
) -> dict[str, Any]:
    mode = cfg.rule_evaluation_mode(rule_id)
    requires_baseline = cfg.rule_requires_baseline(rule_id)
    requires_profile = cfg.rule_requires_profile(rule_id)

    rule_cfg = cfg.rule(rule_id)
    min_days_with_data = rule_cfg.get("min_days_with_data")
    profile_mode = str(rule_cfg.get("profile_mode", "home_specific"))
    uses_default_profile_when_missing = bool(
        rule_cfg.get("uses_default_profile_when_missing", False)
    )

    out: dict[str, Any] = {
        "evaluation_mode": mode,
        "requires_baseline": requires_baseline,
        "requires_profile": requires_profile,
        "evaluation_truth": "FULLY_EVALUATED",
        "gating_reason": None,
        "basis_summary": None,
        "uses_default_profile": False,
        "profile_mode": profile_mode,
        "baseline_ready": None,
        "days_with_data": None,
        "min_days_required": None,
        "coverage_room_bucket": None,
        "coverage_transition": None,
    }

    baseline = None
    if requires_baseline:
        baseline = load_baseline_truth(
            db,
            org_id=org_id,
            home_id=home_id,
            subject_id=subject_id,
        )
        out["baseline_ready"] = baseline["baseline_ready"]
        out["days_with_data"] = baseline["days_with_data"]
        out["min_days_required"] = baseline["min_days_required"]
        out["coverage_room_bucket"] = baseline["coverage_room_bucket"]
        out["coverage_transition"] = baseline["coverage_transition"]

        min_days_gate = (
            int(min_days_with_data)
            if isinstance(min_days_with_data, (int, float, str))
            and str(min_days_with_data).strip().isdigit()
            else baseline["min_days_required"]
        )

        if not baseline["has_status"]:
            out["evaluation_truth"] = "NOT_EVALUATED"
            out["gating_reason"] = "baseline_status_missing"
            out["basis_summary"] = "Ikke vurdert: mangler baseline-status"
            return out

        if not baseline["baseline_ready"]:
            out["evaluation_truth"] = "WEAK_BASIS"
            out["gating_reason"] = "baseline_not_ready"
            out["basis_summary"] = "Svak vurdering: baseline ikke READY"
            return out

        if min_days_gate is not None and baseline["days_with_data"] < int(min_days_gate):
            out["evaluation_truth"] = "WEAK_BASIS"
            out["gating_reason"] = "insufficient_history_days"
            out["basis_summary"] = "Ikke vurdert: mangler nok historikk"
            return out

    if requires_profile:
        if profile_mode == "default_window" and uses_default_profile_when_missing:
            out["evaluation_truth"] = "DEFAULT_PROFILE"
            out["gating_reason"] = "default_profile_window"
            out["basis_summary"] = "Bruker standard nattvindu, ikke personlig boligprofil"
            out["uses_default_profile"] = True
            return out

    return out
