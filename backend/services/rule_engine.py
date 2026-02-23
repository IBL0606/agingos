from __future__ import annotations

import logging
from datetime import datetime, timedelta

from util.time import utcnow

from sqlalchemy.orm import Session


from config.rule_config import load_rule_config
from schemas.deviation_v1 import DeviationV1

from services.rules.registry import RULE_REGISTRY
from services.rules.context import RuleContext

logger = logging.getLogger("rule_engine")


def _call_rule(
    spec, db: Session, since: datetime, until: datetime, now: datetime, rule_id: str,
    *,
    org_id: str = "default",
    home_id: str = "default",
    subject_id: str = "default",
    subject_key: str = "default",
) -> list[DeviationV1]:
    """Adapter: supports both legacy rule signatures and RuleContext-based rules."""
    cfg = load_rule_config()
    params = cfg.rule_params(rule_id)
    ctx = RuleContext(session=db, since=since, until=until, now=now, params=params, org_id=org_id, home_id=home_id, subject_id=subject_id, subject_key=subject_key)
    fn = spec.eval_fn
    try:
        # New style: fn(ctx)
        return fn(ctx)  # type: ignore[misc]
    except TypeError:
        # Legacy: fn(db, since, until, now)
        return fn(db, since=since, until=until, now=now)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Thin-slice rule engine (registry) - én sannhet for beregning av avvik (Avvik v1)
# ---------------------------------------------------------------------------


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
        now = utcnow()

    selected = rule_ids or list(RULE_REGISTRY.keys())

    devs: list[DeviationV1] = []
    for rid in selected:
        spec = RULE_REGISTRY.get(rid)
        if spec is None:
            # Ukjent regel-id; ignorer (kan evt. gjøres strict senere)
            continue
        devs.extend(
            _call_rule(spec, db, since=since, until=until, now=now, rule_id=rid)
        )

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
        now = utcnow()

    cfg = load_rule_config()

    devs: list[DeviationV1] = []

    for rid, spec in RULE_REGISTRY.items():
        enabled = cfg.rule_enabled_in_scheduler(rid)
        if not enabled:
            continue

        lookback = cfg.rule_lookback_minutes(rid)
        since = now - timedelta(minutes=lookback)
        until = now

        devs.extend(
            _call_rule(spec, db, since=since, until=until, now=now, rule_id=rid)
        )

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
