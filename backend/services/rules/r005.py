from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window
from services.rules.context import RuleContext
from services.rules.r009 import eval_r009_ingest_stopped

RULE_ID = "R-005"


def _get_str(p: Dict[str, Any], key: str, default: str) -> str:
    v = p.get(key)
    return str(v) if isinstance(v, (str, int, float)) and str(v) else default


def _get_int(p: Dict[str, Any], key: str, default: int) -> int:
    try:
        return int(p.get(key))
    except Exception:
        return default


def _last_bathroom_presence_on_ts(ctx: RuleContext, room_id: str, since_ts: datetime) -> Optional[datetime]:
    # Find latest presence "on" event in bathroom since since_ts
    rows = (
        ctx.session.query(EventDB)
        .filter(EventDB.org_id == ctx.org_id)
        .filter(EventDB.home_id == ctx.home_id)
        .filter(EventDB.subject_id == ctx.subject_id)
        .filter(EventDB.timestamp >= since_ts)
        .filter(EventDB.timestamp < ctx.until)
        .filter(EventDB.category == "presence")
        .order_by(EventDB.timestamp.desc())
        .all()
    )
    for r in rows:
        if not isinstance(r.payload, dict):
            continue
        room = str(r.payload.get("room_id") or r.payload.get("room") or "")
        if room != room_id:
            continue
        st = r.payload.get("state") or r.payload.get("value")
        if st is None:
            # Conservative: count as activity
            return r.timestamp
        if str(st).lower() == "on":
            return r.timestamp
    return None


def eval_r005_no_bathroom_activity_24h(ctx: RuleContext) -> List[DeviationV1]:
    p = dict(ctx.params or {})
    room_id = _get_str(p, "bathroom_room_id", "baderom")
    lookback_h = _get_int(p, "lookback_hours", 24)

    # Liveness gate via R-009. If ingest stopped, suppress this trend alarm.
    # We pass through relevant params for R-009.
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

    since_ts = ctx.until - timedelta(hours=lookback_h)
    last_ts = _last_bathroom_presence_on_ts(ctx, room_id, since_ts)

    if last_ts is not None:
        return []

    evidence = {
        "room_id": room_id,
        "lookback_hours": lookback_h,
        "since_ts": since_ts.isoformat(),
        "last_bathroom_ts": None,
        "event_ids": [],
        "liveness_gated_by": "R-009",
    }

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=ctx.now,
            severity="LOW",
            title="Ingen aktivitet på badet på lenge",
            explanation="Det er ikke registrert baderomsaktivitet i perioden. Kan indikere endret rutine eller at sensor ikke fanger opp.",
            evidence=evidence,
            window=Window(since=since_ts, until=ctx.until),
        )
    ]


# Backwards-compatible name used by registry import
eval_r005_todo = eval_r005_no_bathroom_activity_24h
