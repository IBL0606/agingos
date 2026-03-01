from __future__ import annotations

from datetime import timedelta
from typing import List

from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window
from services.rules.context import RuleContext

RULE_ID = "R-003"


def _params(ctx: RuleContext) -> dict:
    p = ctx.params or {}
    return p if isinstance(p, dict) else {}


def _followup_minutes(ctx: RuleContext) -> int:
    return int(_params(ctx).get("followup_minutes", 10))


def _door_category(ctx: RuleContext) -> str:
    return str(_params(ctx).get("door_category", "door"))


def _motion_categories(ctx: RuleContext) -> list[str]:
    """
    Prefer new param: motion_categories: ["motion","presence"]
    Back-compat: motion_category: "motion"
    Default: ["motion"]
    """
    p = _params(ctx)
    cats = p.get("motion_categories")
    if isinstance(cats, list) and cats:
        return [str(x) for x in cats]
    cat = p.get("motion_category")
    if isinstance(cat, str) and cat.strip():
        return [cat.strip()]
    return ["motion"]


def _payload_state_keys(ctx: RuleContext) -> list[str]:
    keys = _params(ctx).get("payload_state_keys", ["state", "value"])
    if isinstance(keys, list) and keys:
        return [str(x) for x in keys]
    return ["state", "value"]


def _door_name_keys(ctx: RuleContext) -> list[str]:
    keys = _params(ctx).get("door_name_keys", ["door", "name"])
    if isinstance(keys, list) and keys:
        return [str(x) for x in keys]
    return ["door", "name"]


def _required_door_name(ctx: RuleContext) -> str:
    return str(_params(ctx).get("required_door_name", "front"))


def _door_open_value(ctx: RuleContext) -> str:
    return str(_params(ctx).get("door_open_value", "open"))


def _motion_on_value(ctx: RuleContext) -> str:
    return str(_params(ctx).get("motion_on_value", "on"))


def _get_first(payload: object, keys: list[str]) -> str | None:
    if not isinstance(payload, dict):
        return None
    for k in keys:
        v = payload.get(k)
        if v is not None:
            return str(v)
    return None


def eval_r003_front_door_open_no_motion_after(ctx: RuleContext) -> List[DeviationV1]:
    follow_minutes = _followup_minutes(ctx)

    door_rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.timestamp >= ctx.since)
        .filter(EventDB.timestamp < ctx.until)  # until eksklusiv
        .filter(EventDB.category == _door_category(ctx))
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    required_name = _required_door_name(ctx)
    door_open = _door_open_value(ctx)
    motion_on = _motion_on_value(ctx)
    motion_cats = _motion_categories(ctx)

    triggered = False
    evidence: List[str] = []

    for d in door_rows:
        state = _get_first(d.payload, _payload_state_keys(ctx))
        door_name = _get_first(d.payload, _door_name_keys(ctx))

        # Deterministisk match: configured door open
        if state != door_open or door_name != required_name:
            continue

        follow_until = d.timestamp + timedelta(minutes=follow_minutes)

        motion_rows = (
            ctx.session.query(EventDB)
            .filter(EventDB.timestamp >= d.timestamp)
            .filter(EventDB.timestamp < follow_until)  # follow_until eksklusiv
            .filter(EventDB.category.in_(motion_cats))
            .order_by(EventDB.timestamp.asc())
            .all()
        )

        has_motion_on = False
        for m in motion_rows:
            m_state = _get_first(m.payload, _payload_state_keys(ctx))
            # If motion/presence has explicit state/value, require it to be "on"
            if m_state is None:
                has_motion_on = True
                break
            if m_state == motion_on:
                has_motion_on = True
                break

        if not has_motion_on:
            triggered = True
            evidence.append(str(d.id))
            break

    if not triggered:
        return []

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=ctx.now,
            severity="MEDIUM",
            title="Mulig uvanlig hendelse etter dør",
            explanation=(
                f"Døren ble åpnet, men systemet registrerte ingen aktivitet i de neste {follow_minutes} minuttene. "
                "Det kan være at personen gikk ut, falt, eller at sensorer ikke registrerte aktivitet."
            ),
            evidence=evidence,
            window=Window(since=ctx.since, until=ctx.until),
        )
    ]
