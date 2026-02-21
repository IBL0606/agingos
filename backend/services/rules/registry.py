from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List

from sqlalchemy.orm import Session

from schemas.deviation_v1 import DeviationV1

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
    rule_id: str
    eval_fn: Callable[[Session, datetime, datetime, datetime], List[DeviationV1]]
    description: str


RULE_REGISTRY: Dict[str, RuleSpec] = {
    "R-001": RuleSpec("R-001", eval_r001_no_motion, "No motion in window"),
    "R-002": RuleSpec("R-002", eval_r002_front_door_open_at_night, "Front door open at night"),
    "R-003": RuleSpec("R-003", eval_r003_front_door_open_no_motion_after, "Door open, then no motion"),
    "R-004": RuleSpec("R-004", eval_r004_todo, "TODO stub"),
    "R-005": RuleSpec("R-005", eval_r005_todo, "TODO stub"),
    "R-006": RuleSpec("R-006", eval_r006_todo, "TODO stub"),
    "R-007": RuleSpec("R-007", eval_r007_todo, "TODO stub"),
    "R-008": RuleSpec("R-008", eval_r008_todo, "TODO stub"),
    "R-009": RuleSpec("R-009", eval_r009_todo, "TODO stub"),
    "R-010": RuleSpec("R-010", eval_r010_todo, "TODO stub"),
}
