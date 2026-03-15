from __future__ import annotations

from dataclasses import dataclass

from config.rule_config import RuleConfig
from services.rules.gating import build_rule_truth


@dataclass
class _Result:
    row: dict | None

    def mappings(self):
        return self

    def first(self):
        return self.row


class _DB:
    def __init__(self, row: dict | None):
        self._row = row

    def execute(self, *_args, **_kwargs):
        return _Result(self._row)


def test_baseline_dependent_rule_reports_weak_basis_when_not_ready():
    cfg = RuleConfig(
        raw={
            "rules": {
                "R-001": {
                    "evaluation_mode": "baseline_dependent",
                    "requires_baseline": True,
                }
            }
        }
    )
    db = _DB(
        {
            "baseline_ready": False,
            "min_days_required": 3,
            "days_with_data": 1,
            "room_bucket_rows": 10,
            "room_bucket_supported": 6,
            "transition_rows": 10,
            "transition_supported": 7,
        }
    )

    out = build_rule_truth(
        cfg,
        "R-001",
        db=db,
        org_id="default",
        home_id="default",
        subject_id="default",
    )

    assert out["evaluation_truth"] == "WEAK_BASIS"
    assert out["gating_reason"] == "baseline_not_ready"


def test_profile_dependent_rule_reports_default_profile_mode():
    cfg = RuleConfig(
        raw={
            "rules": {
                "R-002": {
                    "evaluation_mode": "profile_dependent",
                    "requires_profile": True,
                    "profile_mode": "default_window",
                    "uses_default_profile_when_missing": True,
                }
            }
        }
    )

    out = build_rule_truth(
        cfg,
        "R-002",
        db=_DB(None),
        org_id="default",
        home_id="default",
        subject_id="default",
    )

    assert out["evaluation_truth"] == "DEFAULT_PROFILE"
    assert out["uses_default_profile"] is True


def test_independent_rule_stays_fully_evaluated():
    cfg = RuleConfig(
        raw={
            "rules": {
                "R-009": {
                    "evaluation_mode": "independent",
                    "requires_baseline": False,
                    "requires_profile": False,
                }
            }
        }
    )

    out = build_rule_truth(
        cfg,
        "R-009",
        db=_DB(None),
        org_id="default",
        home_id="default",
        subject_id="default",
    )

    assert out["evaluation_truth"] == "FULLY_EVALUATED"
    assert out["gating_reason"] is None


class _DBRaises:
    def execute(self, *_args, **_kwargs):
        raise RuntimeError("UndefinedColumn: min_days_required")


def test_baseline_truth_missing_columns_degrades_without_crash():
    cfg = RuleConfig(
        raw={
            "rules": {
                "R-001": {
                    "evaluation_mode": "baseline_dependent",
                    "requires_baseline": True,
                }
            }
        }
    )

    out = build_rule_truth(
        cfg,
        "R-001",
        db=_DBRaises(),
        org_id="default",
        home_id="default",
        subject_id="default",
    )

    assert out["evaluation_truth"] == "NOT_EVALUATED"
    assert out["gating_reason"] == "baseline_status_missing"
