from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window
from services.rules.context import RuleContext

RULE_ID = "R-004"


def _get_str(p: Dict[str, Any], key: str, default: str) -> str:
    v = p.get(key)
    return str(v) if isinstance(v, (str, int, float)) and str(v) else default


def _get_int(p: Dict[str, Any], key: str, default: int) -> int:
    v = p.get(key)
    try:
        return int(v)
    except Exception:
        return default


def _get_tz_name(p: Dict[str, Any]) -> str:
    return _get_str(p, "tz", "Europe/Oslo")


def _local_hour(dt_utc: datetime, tz_name: str) -> int:
    try:
        from zoneinfo import ZoneInfo

        return dt_utc.astimezone(ZoneInfo(tz_name)).hour
    except Exception:
        return dt_utc.hour


def _is_night(dt_utc: datetime, tz_name: str, night_start: int, night_end: int) -> bool:
    h = _local_hour(dt_utc, tz_name)
    if night_start <= night_end:
        return night_start <= h < night_end
    return (h >= night_start) or (h < night_end)


def _state(payload: object, ctx: RuleContext) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    keys = (
        ctx.params.get("payload_state_keys") if isinstance(ctx.params, dict) else None
    )
    if not (isinstance(keys, list) and keys):
        keys = ["state", "value"]
    for k in keys:
        if k in payload:
            return str(payload.get(k)).lower()
    return None


def _segments_on_off(
    rows: List[EventDB], ctx: RuleContext
) -> List[Tuple[datetime, Optional[datetime], List[str]]]:
    segs: List[Tuple[datetime, Optional[datetime], List[str]]] = []
    on_start: Optional[datetime] = None
    ev_ids: List[str] = []
    for r in rows:
        st = _state(r.payload, ctx)
        if st not in ("on", "off"):
            continue
        if st == "on":
            if on_start is None:
                on_start = r.timestamp
                ev_ids = [str(r.event_id)]
            else:
                ev_ids.append(str(r.event_id))
        else:
            if on_start is not None:
                ev_ids.append(str(r.event_id))
                segs.append((on_start, r.timestamp, list(ev_ids)))
                on_start = None
                ev_ids = []
    if on_start is not None:
        segs.append((on_start, None, list(ev_ids)))
    return segs


def _any_activity_after(
    ctx: RuleContext, after_ts: datetime, silence_minutes: int, exclude_room: str
) -> bool:
    until2 = min(ctx.until, after_ts + timedelta(minutes=silence_minutes))
    if until2 <= after_ts:
        return False
    cats = (
        ctx.params.get("activity_categories") if isinstance(ctx.params, dict) else None
    )
    if not (isinstance(cats, list) and cats):
        cats = ["presence", "motion"]
    rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.org_id == ctx.org_id)
        .filter(EventDB.home_id == ctx.home_id)
        .filter(EventDB.subject_id == ctx.subject_id)
        .filter(EventDB.timestamp >= after_ts)
        .filter(EventDB.timestamp < until2)
        .filter(EventDB.category.in_([str(x) for x in cats]))
        .order_by(EventDB.timestamp.asc())
        .all()
    )
    for r in rows:
        if isinstance(r.payload, dict):
            room = r.payload.get("room_id") or r.payload.get("room")
            if room and str(room) == exclude_room:
                continue
        return True
    return False


def eval_r004_prolonged_bathroom_presence(ctx: RuleContext) -> List[DeviationV1]:
    p = dict(ctx.params or {})
    room_id = _get_str(p, "bathroom_room_id", "baderom")

    day_threshold = _get_int(p, "day_threshold_min", 45)
    night_threshold = _get_int(p, "night_threshold_min", 25)
    stuck_min = _get_int(p, "sensor_stuck_min", 240)
    silence_after = _get_int(p, "silence_after_min", 30)

    night_start = _get_int(p, "night_start_hour", 22)
    night_end = _get_int(p, "night_end_hour", 7)
    tz_name = _get_tz_name(p)

    rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.org_id == ctx.org_id)
        .filter(EventDB.home_id == ctx.home_id)
        .filter(EventDB.subject_id == ctx.subject_id)
        .filter(EventDB.timestamp >= ctx.since)
        .filter(EventDB.timestamp < ctx.until)
        .filter(EventDB.category == "presence")
        .order_by(EventDB.timestamp.asc())
        .all()
    )
    rows = [
        r
        for r in rows
        if isinstance(r.payload, dict)
        and str(r.payload.get("room_id") or r.payload.get("room") or "") == room_id
    ]

    segs = _segments_on_off(rows, ctx)
    if not segs:
        return []

    best: Optional[Dict[str, Any]] = None
    order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

    for start, end, ev_ids in segs:
        end_eff = end or ctx.until
        dur_min = int((end_eff - start).total_seconds() // 60)

        sensor_fault = dur_min >= stuck_min
        if sensor_fault:
            sev = "LOW"
        else:
            in_night = _is_night(start, tz_name, night_start, night_end)
            threshold = night_threshold if in_night else day_threshold
            if dur_min < threshold:
                continue

            sev = "MEDIUM"
            if dur_min >= 90:
                sev = "HIGH"

            if in_night and sev == "MEDIUM":
                sev = "HIGH"

            if end is not None:
                has_activity = _any_activity_after(
                    ctx, end, silence_after, exclude_room=room_id
                )
                if not has_activity and sev == "MEDIUM":
                    sev = "HIGH"

        cand = {
            "start": start,
            "end": end,
            "dur_min": dur_min,
            "event_ids": ev_ids,
            "sensor_fault": sensor_fault,
            "severity": sev,
        }

        if best is None:
            best = cand
        else:
            if order[cand["severity"]] > order[best["severity"]]:
                best = cand
            elif (
                order[cand["severity"]] == order[best["severity"]]
                and cand["dur_min"] > best["dur_min"]
            ):
                best = cand

    if not best:
        return []

    evidence = {
        "room_id": room_id,
        "day_threshold_min": day_threshold,
        "night_threshold_min": night_threshold,
        "sensor_stuck_min": stuck_min,
        "silence_after_min": silence_after,
        "start_ts": best["start"].isoformat(),
        "end_ts": best["end"].isoformat()
        if isinstance(best["end"], datetime)
        else None,
        "observed_minutes": int(best["dur_min"]),
        "event_ids": best["event_ids"],
        "sensor_fault": bool(best["sensor_fault"]),
        "night_start_hour": night_start,
        "night_end_hour": night_end,
        "tz": tz_name,
    }

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=ctx.until,
            severity=str(best["severity"]),
            title="Uvanlig lang tid på badet",
            explanation="Det er registrert sammenhengende tilstedeværelse på badet utover terskelverdien. Sjekk om alt er OK.",
            evidence=evidence,
            window=Window(since=ctx.since, until=ctx.until),
        )
    ]


# Backwards-compatible name used by registry import
eval_r004_todo = eval_r004_prolonged_bathroom_presence
