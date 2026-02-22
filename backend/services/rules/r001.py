from __future__ import annotations

from typing import List

from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window
from services.rules.context import RuleContext

RULE_ID = "R-001"


def _motion_categories(ctx: RuleContext) -> list[str]:
    """
    Prefer new param: motion_categories: ["motion","presence"]
    Back-compat: motion_category: "motion"
    Default: ["motion"]
    """
    p = ctx.params or {}
    cats = p.get("motion_categories")
    if isinstance(cats, list) and cats:
        return [str(x) for x in cats]
    cat = p.get("motion_category")
    if isinstance(cat, str) and cat.strip():
        return [cat.strip()]
    return ["motion"]


def _payload_state_keys(ctx: RuleContext) -> list[str]:
    p = ctx.params or {}
    keys = p.get("payload_state_keys")
    if isinstance(keys, list) and keys:
        return [str(x) for x in keys]
    return ["state", "value"]


def _motion_on_value(ctx: RuleContext) -> str:
    p = ctx.params or {}
    v = p.get("motion_on_value")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return "on"


def _is_active_motion(payload: object, ctx: RuleContext) -> bool:
    """
    For presence/motion we only want to count ACTIVE signals (typically state=="on").
    If state keys are missing, be conservative and count it as motion-like activity.
    """
    if not isinstance(payload, dict):
        return True
    keys = _payload_state_keys(ctx)
    on_v = _motion_on_value(ctx)
    # Try keys in order; if we find a state/value, require match.
    for k in keys:
        if k in payload:
            return str(payload.get(k)) == on_v
    # No state/value keys -> treat as activity.
    return True


def eval_r001_no_motion(ctx: RuleContext) -> List[DeviationV1]:
    cats = _motion_categories(ctx)

    rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.timestamp >= ctx.since)
        .filter(EventDB.timestamp < ctx.until)  # until eksklusiv
        .filter(EventDB.category.in_(cats))
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    # Only count active motion-like signals
    active = [r for r in rows if _is_active_motion(r.payload, ctx)]
    if active:
        return []

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=ctx.now,
            severity="MEDIUM",
            title="Ingen bevegelse registrert i valgt tidsvindu",
            explanation="Det finnes ingen bevegelse-/aktivitetshendelser i vurdert tidsvindu. Sjekk sensor, dekning eller om personen har vært inaktiv/ute.",
            evidence=[],
            window=Window(since=ctx.since, until=ctx.until),
        )
    ]
