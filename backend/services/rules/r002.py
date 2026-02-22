from __future__ import annotations

from datetime import datetime, time
from typing import List

from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window
from services.rules.context import RuleContext

RULE_ID = "R-002"


def _params(ctx: RuleContext) -> dict:
    p = ctx.params or {}
    return p if isinstance(p, dict) else {}


def _category(ctx: RuleContext) -> str:
    p = _params(ctx)
    v = p.get("category")
    return str(v).strip() if isinstance(v, str) and v.strip() else "door"


def _payload_state_keys(ctx: RuleContext) -> list[str]:
    p = _params(ctx)
    keys = p.get("payload_state_keys")
    if isinstance(keys, list) and keys:
        return [str(x) for x in keys]
    return ["state", "value"]


def _trigger_value(ctx: RuleContext) -> str:
    p = _params(ctx)
    v = p.get("trigger_value")
    return str(v).strip() if isinstance(v, str) and v.strip() else "open"


def _night_window(ctx: RuleContext) -> tuple[time, time]:
    """
    Reads night window from ctx.params:
      rules.R-002.params.night_window.start_local_time
      rules.R-002.params.night_window.end_local_time

    Defaults: 23:00:00 -> 06:00:00
    """
    p = _params(ctx)
    w = p.get("night_window", {}) if isinstance(p, dict) else {}
    if not isinstance(w, dict):
        w = {}
    start_s = w.get("start_local_time", "23:00:00")
    end_s = w.get("end_local_time", "06:00:00")
    return time.fromisoformat(start_s), time.fromisoformat(end_s)


def _is_night(ts: datetime, ctx: RuleContext) -> bool:
    start_t, end_t = _night_window(ctx)
    t = ts.time()

    # If the window crosses midnight (e.g. 23:00 -> 06:00)
    if start_t > end_t:
        return (t >= start_t) or (t < end_t)

    # Normal same-day window
    return start_t <= t < end_t


def _event_state(payload: object, ctx: RuleContext) -> str | None:
    if not isinstance(payload, dict):
        return None
    for k in _payload_state_keys(ctx):
        if k in payload:
            v = payload.get(k)
            return None if v is None else str(v)
    return None


def eval_r002_front_door_open_at_night(ctx: RuleContext) -> List[DeviationV1]:
    cat = _category(ctx)
    tv = _trigger_value(ctx)

    rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.timestamp >= ctx.since)
        .filter(EventDB.timestamp < ctx.until)  # until eksklusiv
        .filter(EventDB.category == cat)
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    evidence: List[str] = []
    for r in rows:
        state = _event_state(r.payload, ctx)
        if state == tv and _is_night(r.timestamp, ctx):
            evidence.append(str(r.id))

    if not evidence:
        return []

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=ctx.now,
            severity="HIGH",
            title="Ytterdør åpnet på natt",
            explanation="Det er registrert at ytterdør ble åpnet i nattetid. Sjekk om dette var forventet.",
            evidence=evidence,
            window=Window(since=ctx.since, until=ctx.until),
        )
    ]
