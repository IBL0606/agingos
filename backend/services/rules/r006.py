from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window
from services.rules.context import RuleContext

RULE_ID = "R-006"


def _get_str(p: Dict[str, Any], key: str, default: str) -> str:
    v = p.get(key)
    return str(v) if isinstance(v, (str, int, float)) and str(v) else default


def _get_int(p: Dict[str, Any], key: str, default: int) -> int:
    try:
        return int(p.get(key))
    except Exception:
        return default


def _day_window_utc(until_utc: datetime, tz_name: str, day_start: int, day_end: int) -> tuple[datetime, datetime]:
    # Convert local day window to UTC bounds deterministically.
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
        local = until_utc.astimezone(tz)
        local_date = local.date()
        start_local = datetime(local_date.year, local_date.month, local_date.day, day_start, 0, 0, tzinfo=tz)
        end_local = datetime(local_date.year, local_date.month, local_date.day, day_end, 0, 0, tzinfo=tz)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
    except Exception:
        # Fallback: treat as UTC
        d = until_utc.date()
        start_utc = datetime(d.year, d.month, d.day, day_start, 0, 0, tzinfo=timezone.utc)
        end_utc = datetime(d.year, d.month, d.day, day_end, 0, 0, tzinfo=timezone.utc)
        return start_utc, end_utc


def _has_presence_on(rows: List[EventDB], room_id: str) -> bool:
    for r in rows:
        if not isinstance(r.payload, dict):
            continue
        room = str(r.payload.get("room_id") or r.payload.get("room") or "")
        if room != room_id:
            continue
        st = r.payload.get("state") or r.payload.get("value")
        if st is None:
            return True
        if str(st).lower() == "on":
            return True
    return False


def eval_r006_no_livingroom_daytime_activity(ctx: RuleContext) -> List[DeviationV1]:
    p = dict(ctx.params or {})
    tz_name = _get_str(p, "tz", "Europe/Oslo")
    day_start = _get_int(p, "day_start_hour", 8)
    day_end = _get_int(p, "day_end_hour", 20)

    living_room = _get_str(p, "living_room_id", "stue")
    front_door_room = _get_str(p, "front_door_room_id", "inngang")

    w_since, w_until = _day_window_utc(ctx.until, tz_name, day_start, day_end)

    # Query presence + door in window (single pass)
    rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.org_id == ctx.org_id)
        .filter(EventDB.home_id == ctx.home_id)
        .filter(EventDB.subject_id == ctx.subject_id)
        .filter(EventDB.timestamp >= w_since)
        .filter(EventDB.timestamp < w_until)
        .filter(EventDB.category.in_(["presence", "door"]))
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    # "Mulig ute" suppression:
    # If front door event exists AND there is presence in any other room in the window -> do not trigger.
    door_seen = False
    other_presence = False

    for r in rows:
        if not isinstance(r.payload, dict):
            continue
        room = str(r.payload.get("room_id") or r.payload.get("room") or "")
        if r.category == "door" and room == front_door_room:
            door_seen = True
        if r.category == "presence":
            if room and room != living_room:
                st = r.payload.get("state") or r.payload.get("value")
                if st is None or str(st).lower() == "on":
                    other_presence = True

    if door_seen and other_presence:
        return []

    # Trigger if NO presence on in living room during day window
    presence_rows = [r for r in rows if r.category == "presence"]
    if _has_presence_on(presence_rows, living_room):
        return []

    evidence = {
        "tz": tz_name,
        "day_start_hour": day_start,
        "day_end_hour": day_end,
        "living_room_id": living_room,
        "front_door_room_id": front_door_room,
        "door_seen": door_seen,
        "other_presence": other_presence,
        "event_ids": [str(r.event_id) for r in rows[:50]],  # cap
    }

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=ctx.now,
            severity="LOW",
            title="Ingen aktivitet i stuen på dagtid",
            explanation="Det er ikke registrert aktivitet i stuen i dagvinduet. Kan indikere at personen ikke er oppe, eller at rutinen er endret.",
            evidence=evidence,
            window=Window(since=w_since, until=w_until),
        )
    ]


# Backwards-compatible name used by registry import
eval_r006_todo = eval_r006_no_livingroom_daytime_activity
