from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

logger = logging.getLogger("rule_engine")


# ---------------------------------------------------------------------------
# Thin-slice rule engine (registry) - én sannhet for beregning av avvik (Avvik v1)
# ---------------------------------------------------------------------------

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from config.rule_config import load_rule_config
from schemas.deviation_v1 import DeviationV1

from services.rules.r001 import eval_r001_no_motion
from services.rules.r002 import eval_r002_front_door_open_at_night
from services.rules.r003 import eval_r003_front_door_open_no_motion_after


@dataclass(frozen=True)
class RuleSpec:
    """
    Regelspesifikasjon for registry.

    - rule_id: "R-001", "R-002", ...
    - eval_fn: funksjon som evaluerer regelen og returnerer en liste med DeviationV1
    - description: kort menneskelig beskrivelse (for docs/feilsøking)
    """
    rule_id: str
    eval_fn: Callable[[Session, datetime, datetime, datetime], List[DeviationV1]]
    description: str


# Registry-prinsipp:
# - Nye regler legges til her (én gang), og brukes deretter av routes og scheduler.
RULE_REGISTRY: Dict[str, RuleSpec] = {
    "R-001": RuleSpec(
        rule_id="R-001",
        eval_fn=eval_r001_no_motion,
        description="Ingen bevegelse i valgt tidsvindu",
    ),
    "R-002": RuleSpec(
        rule_id="R-002",
        eval_fn=eval_r002_front_door_open_at_night,
        description="Ytterdør åpnet på natt",
    ),
    "R-003": RuleSpec(
        rule_id="R-003",
        eval_fn=eval_r003_front_door_open_no_motion_after,
        description="Dør åpnet, men ingen bevegelse etterpå",
    ),
}


def evaluate_rules(
    db: Session,
    since: datetime,
    until: datetime,
    now: datetime | None = None,
    rule_ids: list[str] | None = None,
) -> list[DeviationV1]:
    """
    Evaluerer regler via registry og returnerer beregnede avvik (Avvik v1).

    Parametre:
      - db: SQLAlchemy Session (leser events fra EventDB)
      - since/until: evalueringsvindu [since, until) der until er eksklusiv
      - now: tidspunktet deviation.timestamp settes til (default: nå i UTC)
      - rule_ids: hvis satt, evaluer kun disse (f.eks. ["R-002"])

    Forventninger:
      - Regelimplementasjoner er deterministiske gitt samme (db, since, until, now).

    Retur:
      - Liste med DeviationV1, aggregerte i registry-rekkefølge (rule_ids hvis gitt).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    selected = rule_ids or list(RULE_REGISTRY.keys())

    devs: list[DeviationV1] = []
    for rid in selected:
        spec = RULE_REGISTRY.get(rid)
        if spec is None:
            # Ukjent regel-id; ignorer (kan evt. gjøres strict senere)
            continue
        devs.extend(spec.eval_fn(db, since=since, until=until, now=now))

    return devs


def evaluate_rules_for_scheduler(
    db: Session,
    now: datetime | None = None,
) -> list[DeviationV1]:
    """
    Scheduler-evaluering via registry:

    - Respekterer rules.<id>.enabled_in_scheduler == true
    - Bruker rules.<id>.lookback_minutes (fallback til defaults.lookback_minutes, fallback 60)
    - Evaluerer hvert rule_id i sitt eget vindu: [now-lookback, now)

    Return:
      - Liste med DeviationV1 (ingen persist her; kun beregning)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    cfg = load_rule_config()

    devs: list[DeviationV1] = []

    for rid, spec in RULE_REGISTRY.items():
        enabled = cfg.rule_enabled_in_scheduler(rid)
        if not enabled:
            continue

        lookback = cfg.rule_lookback_minutes(rid)
        since = now - timedelta(minutes=lookback)
        until = now

        devs.extend(spec.eval_fn(db, since=since, until=until, now=now))

    return devs



# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

def run_rules(db: Session, now: datetime | None = None) -> list[DeviationV1]:
    """
    Bakoverkompatibel wrapper.

    Historisk kjørte denne funksjonen en separat, DB-backed regelmotor (RuleType) og persisterte deviations.
    Regelberegning er nå registry-basert (evaluate_rules / evaluate_rules_for_scheduler), og persistering
    i scheduler-flow håndteres i services/scheduler.py.

    Return:
      - Liste med beregnede DeviationV1 for scheduler-enabled regler (enabled_in_scheduler=true).
    """
    return evaluate_rules_for_scheduler(db, now=now)

