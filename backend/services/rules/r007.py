from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window
from services.rules.context import RuleContext

RULE_ID = "R-007"


def _get_str(p: Dict[str, Any], key: str, default: str) -> str:
    v = p.get(key)
    return str(v) if isinstance(v, (str, int, float)) and str(v) else default


def _get_int(p: Dict[str, Any], key: str, default: int) -> int:
    try:
        return int(p.get(key))
    except Exception:
        return default


def _night_window_utc(
    until_utc: datetime, tz_name: str, night_start: int, night_end: int
) -> tuple[datetime, datetime]:
    # Night window anchored to the local date of until_utc.
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(tz_name)
        local = until_utc.astimezone(tz)
        d = local.date()
        # window spans midnight; assume night_start > night_end (e.g. 22 -> 7)
        start_local = datetime(d.year, d.month, d.day, night_start, 0, 0, tzinfo=tz)
        # end is on next day if spans midnight
        if night_start > night_end:
            from datetime import timedelta

            d2 = d + timedelta(days=1)
            end_local = datetime(d2.year, d2.month, d2.day, night_end, 0, 0, tzinfo=tz)
        else:
            end_local = datetime(d.year, d.month, d.day, night_end, 0, 0, tzinfo=tz)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
    except Exception:
        # fallback: treat as UTC, night_start > night_end => crosses midnight
        d = until_utc.date()
        start_utc = datetime(
            d.year, d.month, d.day, night_start, 0, 0, tzinfo=timezone.utc
        )
        if night_start > night_end:
            from datetime import timedelta

            d2 = d + timedelta(days=1)
            end_utc = datetime(
                d2.year, d2.month, d2.day, night_end, 0, 0, tzinfo=timezone.utc
            )
        else:
            end_utc = datetime(
                d.year, d.month, d.day, night_end, 0, 0, tzinfo=timezone.utc
            )
        return start_utc, end_utc


def _state_on(payload: object) -> bool:
    if not isinstance(payload, dict):
        return True
    st = payload.get("state") or payload.get("value")
    if st is None:
        return True
    return str(st).lower() == "on"


def _room(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("room_id") or payload.get("room") or "")


def eval_r007_night_wandering_room_switches(ctx: RuleContext) -> List[DeviationV1]:
    p = dict(ctx.params or {})
    tz_name = _get_str(p, "tz", "Europe/Oslo")
    night_start = _get_int(p, "night_start_hour", 22)
    night_end = _get_int(p, "night_end_hour", 7)

    switch_gap_max = _get_int(p, "switch_gap_max_min", 10)
    switch_threshold = _get_int(p, "switch_threshold", 6)
    front_door_room = _get_str(p, "front_door_room_id", "inngang")

    w_since, w_until = _night_window_utc(ctx.until, tz_name, night_start, night_end)

    cats = p.get("activity_categories")
    if isinstance(cats, list) and cats:
        activity_categories = [str(x) for x in cats]
    else:
        activity_categories = ["presence", "motion"]

    rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.org_id == ctx.org_id)
        .filter(EventDB.home_id == ctx.home_id)
        .filter(EventDB.subject_id == ctx.subject_id)
        .filter(EventDB.timestamp >= w_since)
        .filter(EventDB.timestamp < w_until)
        .filter(EventDB.category.in_(activity_categories + ["door"]))
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    # detect door involvement
    door_involved = any(
        r.category == "door" and _room(r.payload) == front_door_room for r in rows
    )

    # Build ordered room activity timeline (active signals only)
    timeline: List[Tuple[datetime, str, str]] = []
    for r in rows:
        if r.category not in activity_categories:
            continue
        if not _state_on(r.payload):
            continue
        room = _room(r.payload)
        if not room:
            continue
        timeline.append((r.timestamp, room, str(r.event_id)))

    if len(timeline) < 2:
        return []

    # Count room switches within gap
    switches = 0
    switch_ids: List[str] = []
    last_ts, last_room, _ = timeline[0]
    for ts, room, eid in timeline[1:]:
        dt_min = int((ts - last_ts).total_seconds() // 60)
        if dt_min <= switch_gap_max and room != last_room:
            switches += 1
            switch_ids.append(eid)
            last_ts, last_room = ts, room
        else:
            last_ts, last_room = ts, room

    if switches < switch_threshold:
        return []

    sev = "HIGH" if door_involved else "MEDIUM"

    evidence = {
        "tz": tz_name,
        "night_start_hour": night_start,
        "night_end_hour": night_end,
        "switch_gap_max_min": switch_gap_max,
        "switch_threshold": switch_threshold,
        "room_switches": switches,
        "door_involved": door_involved,
        "front_door_room_id": front_door_room,
        "event_ids": switch_ids[:100],
    }

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=ctx.now,
            severity=sev,
            title="Uvanlig mye aktivitet på natt",
            explanation="Mange romskifter på natt kan indikere uro eller desorientering. Følg med og vurder tiltak.",
            evidence=evidence,
            window=Window(since=w_since, until=w_until),
        )
    ]


eval_r007_todo = eval_r007_night_wandering_room_switches
