from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window
from services.rules.context import RuleContext

RULE_ID = "R-008"


def _get_str(p: Dict[str, Any], key: str, default: str) -> str:
    v = p.get(key)
    return str(v) if isinstance(v, (str, int, float)) and str(v) else default


def _get_int(p: Dict[str, Any], key: str, default: int) -> int:
    try:
        return int(p.get(key))
    except Exception:
        return default


def _room(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("room_id") or payload.get("room") or "")


def _is_night(until_utc: datetime, tz_name: str, night_start: int, night_end: int) -> bool:
    """
    True if until_utc falls within the configured local night window.
    Supports windows that span midnight (e.g. 22 -> 7).
    Deterministic: uses only until_utc + params.
    """
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(tz_name)
        h = until_utc.astimezone(tz).hour
    except Exception:
        h = until_utc.astimezone(timezone.utc).hour

    if night_start == night_end:
        # degenerate: treat as always-night
        return True
    if night_start > night_end:
        # spans midnight
        return (h >= night_start) or (h < night_end)
    # same-day window
    return (h >= night_start) and (h < night_end)


def _bump_severity(sev: str) -> str:
    s = str(sev or "").upper()
    if s == "LOW":
        return "MEDIUM"
    if s == "MEDIUM":
        return "HIGH"
    return "HIGH"


def _has_any_activity_after(
    ctx: RuleContext,
    *,
    after_ts: datetime,
    until_ts: datetime,
    categories: List[str],
) -> bool:
    rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.org_id == ctx.org_id)
        .filter(EventDB.home_id == ctx.home_id)
        .filter(EventDB.subject_id == ctx.subject_id)
        .filter(EventDB.timestamp >= after_ts)
        .filter(EventDB.timestamp < until_ts)
        .filter(EventDB.category.in_(categories))
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    # Defensive filtering in Python as well (important for unit tests that stub DB filtering).
    cats = set(str(c) for c in categories)

    # Conservative: any qualifying row counts as "activity" unless it is clearly an "off" state.
    for r in rows:
        ts = getattr(r, "timestamp", None)
        if ts is None or ts < after_ts or ts >= until_ts:
            continue
        cat = str(getattr(r, "category", "") or "")
        if cat not in cats:
            continue

        payload = getattr(r, "payload", None)
        if not isinstance(payload, dict):
            return True
        st = payload.get("state") or payload.get("value")
        if st is None:
            return True
        if str(st).lower() in ("on", "open", "true", "1"):
            return True
    return False


def eval_r008_door_burst(ctx: RuleContext) -> List[DeviationV1]:
    p = dict(ctx.params or {})

    front_door_room = _get_str(p, "front_door_room_id", "inngang")
    lookback_min = _get_int(p, "lookback_minutes", 30)
    burst_threshold = _get_int(p, "burst_threshold", 6)

    tz_name = _get_str(p, "tz", "Europe/Oslo")
    night_start = _get_int(p, "night_start_hour", 22)
    night_end = _get_int(p, "night_end_hour", 7)

    quiet_after_min = _get_int(p, "quiet_after_minutes", 0)
    quiet_cats = p.get("quiet_categories")
    if isinstance(quiet_cats, list) and quiet_cats:
        quiet_categories = [str(x) for x in quiet_cats]
    else:
        quiet_categories = ["presence", "motion"]

    w_since = ctx.until - timedelta(minutes=lookback_min)
    w_until = ctx.until

    # Fetch door events in lookback window
    door_rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.org_id == ctx.org_id)
        .filter(EventDB.home_id == ctx.home_id)
        .filter(EventDB.subject_id == ctx.subject_id)
        .filter(EventDB.timestamp >= w_since)
        .filter(EventDB.timestamp < w_until)
        .filter(EventDB.category == "door")
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    door_ids: List[str] = []
    last_door_ts: Optional[datetime] = None
    for r in door_rows:
        if _room(r.payload) != front_door_room:
            continue
        door_ids.append(str(r.event_id))
        last_door_ts = r.timestamp

    door_count = len(door_ids)
    if door_count < burst_threshold:
        return []

    sev = "MEDIUM"
    night = _is_night(ctx.until, tz_name, night_start, night_end)
    if night:
        sev = _bump_severity(sev)

    # Quiet-after boost: if no presence/motion immediately after last door activity, bump severity
    quiet_after = False
    quiet_window_since = None
    quiet_window_until = None
    if last_door_ts is not None and quiet_after_min > 0:
        quiet_window_since = last_door_ts
        quiet_window_until = min(ctx.until, last_door_ts + timedelta(minutes=quiet_after_min))
        has_activity = _has_any_activity_after(
            ctx,
            after_ts=quiet_window_since,
            until_ts=quiet_window_until,
            categories=quiet_categories,
        )
        quiet_after = not has_activity
        if quiet_after:
            sev = _bump_severity(sev)

    evidence: Dict[str, Any] = {
        "front_door_room_id": front_door_room,
        "lookback_minutes": lookback_min,
        "burst_threshold": burst_threshold,
        "door_event_count": door_count,
        "door_event_ids": door_ids[:200],
        "night": night,
        "tz": tz_name,
        "night_start_hour": night_start,
        "night_end_hour": night_end,
        "quiet_after_minutes": quiet_after_min,
        "quiet_categories": quiet_categories,
        "quiet_after": quiet_after,
        "last_door_ts": last_door_ts.isoformat() if last_door_ts else None,
        "quiet_window": {
            "since": quiet_window_since.isoformat() if quiet_window_since else None,
            "until": quiet_window_until.isoformat() if quiet_window_until else None,
        },
    }

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=ctx.now,
            severity=sev,
            title="Mange dørhendelser på kort tid",
            explanation="Mange dørhendelser på kort tid kan tyde på uro, forvirring eller at noen forlater/ankommer ofte. Følg med og vurder tiltak.",
            evidence=evidence,
            window=Window(since=w_since, until=w_until),
        )
    ]


# Backwards-compatible name used by registry import
eval_r008_todo = eval_r008_door_burst
