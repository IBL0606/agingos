from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from models.db_event import EventDB
from schemas.deviation_v1 import DeviationV1, Window
from services.rules.context import RuleContext

RULE_ID = "R-009"


def _get_int(p: Dict[str, Any], key: str, default: int) -> int:
    try:
        return int(p.get(key))
    except Exception:
        return default


def _last_event_ts(ctx: RuleContext, categories: Optional[List[str]] = None) -> Optional[datetime]:
    q = ctx.session.query(EventDB).order_by(EventDB.timestamp.desc())
    q = q.filter(EventDB.org_id == ctx.org_id)
    q = q.filter(EventDB.home_id == ctx.home_id)
    q = q.filter(EventDB.subject_id == ctx.subject_id)
    if categories:
        q = q.filter(EventDB.category.in_(categories))
    row = q.first()
    return row.timestamp if row else None


def eval_r009_ingest_stopped(ctx: RuleContext) -> List[DeviationV1]:
    p = dict(ctx.params or {})
    max_age_min = _get_int(p, "max_age_minutes", 15)

    cats = p.get("liveness_categories")
    if isinstance(cats, list) and cats:
        categories = [str(x) for x in cats]
    else:
        categories = ["presence", "motion", "door", "heartbeat"]

    last_ts = _last_event_ts(ctx, categories=categories)
    lag_min = None if not last_ts else int((ctx.now - last_ts).total_seconds() // 60)

    if last_ts and lag_min is not None and lag_min <= max_age_min:
        return []

    evidence = {
        "max_age_minutes": max_age_min,
        "last_event_ts": last_ts.isoformat() if last_ts else None,
        "lag_minutes": lag_min,
        "categories": categories,
        "event_ids": [],
    }

    return [
        DeviationV1(
            rule_id=RULE_ID,
            timestamp=ctx.now,
            severity="HIGH",
            title="Datainnhenting har stoppet",
            explanation="Systemet har ikke mottatt nye hendelser innen forventet tid. Sjekk sensorer, nettverk eller integrasjon.",
            evidence=evidence,
            window=Window(since=ctx.since, until=ctx.until),
        )
    ]


# Backwards-compatible name used by registry import
eval_r009_todo = eval_r009_ingest_stopped
