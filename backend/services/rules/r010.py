from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window
from services.rules.context import RuleContext
from services.rules.r009 import eval_r009_ingest_stopped

RULE_ID = "R-010"


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


def _state(payload: object) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    v = payload.get("state")
    if v is None:
        v = payload.get("value")
    if v is None:
        return None
    return str(v).lower()


def _severity_for_room(room_id: str, p: Dict[str, Any]) -> str:
    # Defaults per spec (can be overridden by params).
    # MEDIUM rooms: baderom/inngang; LOW rooms: stue/soverom
    med_rooms = p.get("medium_rooms")
    low_rooms = p.get("low_rooms")
    if isinstance(med_rooms, list) and med_rooms:
        medium_set = {str(x) for x in med_rooms}
    else:
        medium_set = {"baderom", "inngang"}
    if isinstance(low_rooms, list) and low_rooms:
        low_set = {str(x) for x in low_rooms}
    else:
        low_set = {"stue", "soverom"}

    if room_id in medium_set:
        return "MEDIUM"
    if room_id in low_set:
        return "LOW"
    return "LOW"


def _max_sev(a: str, b: str) -> str:
    rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    ra = rank.get(str(a).upper(), 1)
    rb = rank.get(str(b).upper(), 1)
    return a if ra >= rb else b


def _iter_presence_events(
    rows: List[Any], *, since_ts: datetime, until_ts: datetime
) -> List[Any]:
    """Defensive filtering for test stubs that do not apply SQLAlchemy filters/order_by."""
    out = []
    for r in rows:
        ts = getattr(r, "timestamp", None)
        if ts is None or ts < since_ts or ts >= until_ts:
            continue
        cat = str(getattr(r, "category", "") or "")
        if cat != "presence":
            continue
        out.append(r)
    return out


def _find_last_presence_on_per_room(
    ctx: RuleContext, since_ts: datetime
) -> Dict[str, Any]:
    # Query presence events (since_ts..until), scan latest->earliest for last "on" per room.
    rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.timestamp >= since_ts)
        .filter(EventDB.timestamp < ctx.until)
        .filter(EventDB.category == "presence")
        .order_by(EventDB.timestamp.desc())
        .all()
    )

    filtered = _iter_presence_events(rows, since_ts=since_ts, until_ts=ctx.until)
    filtered.sort(key=lambda r: r.timestamp, reverse=True)

    out: Dict[str, Any] = {}
    for r in filtered:
        room = _room(getattr(r, "payload", None))
        if not room or room in out:
            continue
        st = _state(getattr(r, "payload", None))
        if st == "on":
            out[room] = r
    return out


def _has_presence_off_after(ctx: RuleContext, room_id: str, after_ts: datetime) -> bool:
    # Look for a presence "off" after after_ts (until ctx.until).
    rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.timestamp >= after_ts)
        .filter(EventDB.timestamp < ctx.until)
        .filter(EventDB.category == "presence")
        .order_by(EventDB.timestamp.asc())
        .all()
    )

    filtered = _iter_presence_events(rows, since_ts=after_ts, until_ts=ctx.until)
    filtered.sort(key=lambda r: r.timestamp)

    for r in filtered:
        if _room(getattr(r, "payload", None)) != room_id:
            continue
        st = _state(getattr(r, "payload", None))
        if st == "off":
            return True
    return False


def eval_r010_sensor_stuck_room_stuck(ctx: RuleContext) -> List[DeviationV1]:
    p = dict(ctx.params or {})

    stuck_min = _get_int(p, "stuck_minutes", 240)
    lookback_min = _get_int(p, "lookback_minutes", stuck_min + 60)

    # Liveness gate via R-009. If ingest stopped, suppress stuck alarms.
    r009_params = {
        "max_age_minutes": _get_int(p, "liveness_max_age_minutes", 15),
        "liveness_categories": p.get("liveness_categories"),
    }
    if eval_r009_ingest_stopped(
        RuleContext(
            session=ctx.session,
            since=ctx.since,
            until=ctx.until,
            now=ctx.now,
            params=r009_params,
            org_id=ctx.org_id,
            home_id=ctx.home_id,
            subject_id=ctx.subject_id,
            subject_key=ctx.subject_key,
        )
    ):
        return []

    since_ts = ctx.until - timedelta(minutes=lookback_min)

    last_on_by_room = _find_last_presence_on_per_room(ctx, since_ts)
    if not last_on_by_room:
        return []

    stuck_rooms: List[str] = []
    per_room: Dict[str, Any] = {}
    overall_sev = "LOW"

    cutoff = ctx.until - timedelta(minutes=stuck_min)

    for room_id, last_on in last_on_by_room.items():
        if last_on.timestamp > cutoff:
            continue  # not old enough to be stuck

        # If we have an OFF after the ON, it is not stuck.
        if _has_presence_off_after(ctx, room_id, last_on.timestamp):
            continue

        sev_room = _severity_for_room(room_id, p)
        overall_sev = _max_sev(overall_sev, sev_room)

        stuck_rooms.append(room_id)
        per_room[room_id] = {
            "severity": sev_room,
            "last_on_ts": last_on.timestamp.isoformat(),
            "last_on_event_id": str(getattr(last_on, "event_id", "")),
        }

    if not stuck_rooms:
        return []

    evidence: Dict[str, Any] = {
        "stuck_minutes": stuck_min,
        "lookback_minutes": lookback_min,
        "cutoff_ts": cutoff.isoformat(),
        "stuck_rooms": sorted(stuck_rooms),
        "per_room": per_room,
        "liveness_gated_by": "R-009",
    }

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=ctx.now,
            severity=overall_sev,
            title="Sensor kan ha hengt seg",
            explanation='Hvis en sensor står på "tilstede" lenge uten å slå av, kan sensoren eller tolkningen være feil. Sjekk rommene som er listet og vurder tiltak.',
            evidence=evidence,
            window=Window(since=since_ts, until=ctx.until),
        )
    ]


# Backwards-compatible name used by registry import
eval_r010_todo = eval_r010_sensor_stuck_room_stuck
