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
