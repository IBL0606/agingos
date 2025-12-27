from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "rules.yaml"


@dataclass(frozen=True)
class RuleConfig:
    raw: Dict[str, Any]

    def scheduler_interval_minutes(self) -> int:
        return int(self.raw.get("scheduler", {}).get("interval_minutes", 1))

    def scheduler_default_subject_key(self) -> str:
        return str(self.raw.get("scheduler", {}).get("default_subject_key", "default"))

    def defaults_lookback_minutes(self) -> int:
        defaults = self.raw.get("defaults", {}) if isinstance(self.raw, dict) else {}
        return int(defaults.get("lookback_minutes", 60))

    def rule_enabled_in_scheduler(self, rule_id: str) -> bool:
        # Semantikk: default False hvis ikke satt (regelen er "off" i scheduler/persist-flow).
        r = self.rule(rule_id)
        return bool(r.get("enabled_in_scheduler", False))

    def rule_lookback_minutes(self, rule_id: str) -> int:
        # Semantikk: rule.lookback_minutes -> defaults.lookback_minutes -> 60
        r = self.rule(rule_id)
        if "lookback_minutes" in r:
            try:
                return int(r["lookback_minutes"])
            except Exception:
                pass
        return self.defaults_lookback_minutes()

    def defaults_expire_after_minutes(self) -> int:
        defaults = self.raw.get("defaults", {}) if isinstance(self.raw, dict) else {}
        return int(defaults.get("expire_after_minutes", 60))

    def rule_expire_after_minutes(self, rule_id: str) -> int:
        r = self.rule(rule_id)
        if "expire_after_minutes" in r:
            return int(r["expire_after_minutes"])
        return self.defaults_expire_after_minutes()

    def rule(self, rule_id: str) -> Dict[str, Any]:
        return dict(self.raw.get("rules", {}).get(rule_id, {}))

    def rule_params(self, rule_id: str) -> Dict[str, Any]:
        return dict(self.rule(rule_id).get("params", {}))


_cached: Optional[RuleConfig] = None


def load_rule_config(path: Path | None = None) -> RuleConfig:
    global _cached
    if _cached is not None:
        return _cached

    p = path or DEFAULT_CONFIG_PATH
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    _cached = RuleConfig(raw=data)
    return _cached
