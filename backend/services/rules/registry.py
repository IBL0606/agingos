from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


from services.rules.r001 import eval_r001_no_motion
from services.rules.r002 import eval_r002_front_door_open_at_night
from services.rules.r003 import eval_r003_front_door_open_no_motion_after

from services.rules.r004 import eval_r004_todo
from services.rules.r005 import eval_r005_todo
from services.rules.r006 import eval_r006_todo
from services.rules.r007 import eval_r007_todo
from services.rules.r008 import eval_r008_todo
from services.rules.r009 import eval_r009_todo
from services.rules.r010 import eval_r010_todo


@dataclass(frozen=True)
class RuleSpec:
    id: str
    eval_fn: Any  # Callable[[RuleContext], List[DeviationV1]] OR legacy Callable[[Session, datetime, datetime, datetime], List[DeviationV1]]
    description: str
    category: str
    version: str


RULE_REGISTRY: Dict[str, RuleSpec] = {
    "R-001": RuleSpec(
        id="R-001",
        eval_fn=eval_r001_no_motion,
        description="No motion in window",
        category="activity",
        version="v1",
    ),
    "R-002": RuleSpec(
        id="R-002",
        eval_fn=eval_r002_front_door_open_at_night,
        description="Front door open at night",
        category="door",
        version="v1",
    ),
    "R-003": RuleSpec(
        id="R-003",
        eval_fn=eval_r003_front_door_open_no_motion_after,
        description="Door open, then no motion",
        category="door",
        version="v1",
    ),
    "R-004": RuleSpec(
        id="R-004",
        eval_fn=eval_r004_todo,
        description="TODO stub",
        category="stub",
        version="v0",
    ),
    "R-005": RuleSpec(
        id="R-005",
        eval_fn=eval_r005_todo,
        description="TODO stub",
        category="stub",
        version="v0",
    ),
    "R-006": RuleSpec(
        id="R-006",
        eval_fn=eval_r006_todo,
        description="TODO stub",
        category="stub",
        version="v0",
    ),
    "R-007": RuleSpec(
        id="R-007",
        eval_fn=eval_r007_todo,
        description="TODO stub",
        category="stub",
        version="v0",
    ),
    "R-008": RuleSpec(
        id="R-008",
        eval_fn=eval_r008_todo,
        description="TODO stub",
        category="stub",
        version="v0",
    ),
    "R-009": RuleSpec(
        id="R-009",
        eval_fn=eval_r009_todo,
        description="TODO stub",
        category="stub",
        version="v0",
    ),
    "R-010": RuleSpec(
        id="R-010",
        eval_fn=eval_r010_todo,
        description="TODO stub",
        category="stub",
        version="v0",
    ),
}
