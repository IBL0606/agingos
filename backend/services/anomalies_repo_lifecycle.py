from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.anomaly_episode import AnomalyEpisode


def _jsonable(x):
    """Make nested structures JSON-serializable (convert date/datetime to ISO strings)."""
    from datetime import date, datetime
    if isinstance(x, (datetime, date)):
        return x.isoformat()
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    return x



def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _level_to_text(level: Any) -> str:
    # Accept either existing text, or legacy smallint levels.
    if isinstance(level, str):
        return level.upper()
    try:
        lv = int(level)
    except Exception:
        return "UNKNOWN"
    if lv >= 2:
        return "RED"
    if lv == 1:
        return "YELLOW"
    return "GREEN"

def _level_to_int(level: Any) -> int:
    # Accept either text ("GREEN"/"YELLOW"/"RED") or int-like
    if isinstance(level, str):
        t = level.upper()
        if t == "RED":
            return 2
        if t == "YELLOW":
            return 1
        return 0
    try:
        return int(level)
    except Exception:
        return 0



def _should_open(level_text: str) -> bool:
    return level_text in ("YELLOW", "RED")


def _is_green(level_text: str) -> bool:
    return level_text == "GREEN"


def _should_close_by_green_streak(green_streak: int, *, n: int = 3) -> bool:
    return green_streak >= n


def _should_close_by_timeout(
    last_bucket: Optional[datetime], *, now: datetime, timeout_minutes: int = 90
) -> bool:
    if last_bucket is None:
        return False
    age_s = (now - last_bucket).total_seconds()
    return age_s >= timeout_minutes * 60


def upsert_bucket_result(
    db: Session,
    *,
    room: str,
    bucket_start: datetime,
    bucket_end: datetime,
    score_total: float,
    level: Any,
    reasons: list[dict[str, Any]],
    reasons_summary: Optional[dict[str, Any]] = None,
    close_green_n: int = 3,
    close_timeout_minutes: int = 90,
) -> Optional[AnomalyEpisode]:
    """
    Idempotent lifecycle updater for anomaly episodes.

    - locks existing active episode row (FOR UPDATE)
    - updates peak/last/green_streak/reasons
    - deterministically closes when criteria met
    - opens new episode only if level is YELLOW/RED and no active exists

    Returns the affected episode or None (if nothing happened).
    """
    room_n = room.strip().lower()
    level_text = _level_to_text(level)
    level_int = _level_to_int(level)
    now = _utc_now()

    # Lock current active episode for this room, if any.
    active_ep = (
        db.execute(
            select(AnomalyEpisode)
            .where(AnomalyEpisode.room == room_n, AnomalyEpisode.end_ts.is_(None))
            .with_for_update()
        )
        .scalars()
        .first()
    )

    # If no active episode: only open on YELLOW/RED
    if active_ep is None:
        if not _should_open(level_text):
            return None
        ep = AnomalyEpisode(
            room=room_n,
            start_ts=bucket_start,
            end_ts=None,
            start_bucket=bucket_start,
            last_bucket=bucket_start,
            peak_bucket=bucket_start,
            peak_score=score_total,
            last_score=score_total,
            last_level=level_text,
            score_total=score_total,
            peak_bucket_start_ts=bucket_start,
            peak_bucket_score=score_total,
            green_streak=0,
            bucket_count=1,
            reasons_last=_jsonable(reasons),
            reasons_peak=_jsonable(reasons_summary or reasons),
            level=level_int,
            score_intensity=0.0,
            score_sequence=0.0,
            score_event=0.0,
        )
        db.add(ep)
        db.flush()  # assigns id
        return ep

    # Idempotency: skip if we already processed this bucket for the active episode
    if active_ep.last_bucket is not None and bucket_start <= active_ep.last_bucket:
        active_ep._noop = True  # runtime flag for route action classification
        return active_ep

    # Update last*
    active_ep.last_bucket = bucket_start
    active_ep.last_score = score_total
    active_ep.score_total = score_total
    active_ep.last_level = level_text
    active_ep.level = level_int
    active_ep.reasons_last = _jsonable(reasons)
    active_ep.bucket_count = int(active_ep.bucket_count or 0) + 1
    active_ep.updated_at = now

    # Update peak if needed
    if active_ep.peak_score is None or score_total > float(active_ep.peak_score):
        active_ep.peak_score = score_total
        active_ep.peak_bucket_score = score_total
        active_ep.peak_bucket = bucket_start
        active_ep.peak_bucket_start_ts = bucket_start
        active_ep.reasons_peak = _jsonable(reasons_summary or reasons)

    # Green streak
    if _is_green(level_text):
        active_ep.green_streak = int(active_ep.green_streak or 0) + 1
    else:
        active_ep.green_streak = 0

    # Close rules (priority: timeout, then green streak)
    if _should_close_by_timeout(active_ep.last_bucket, now=now, timeout_minutes=close_timeout_minutes):
        active_ep.end_ts = bucket_end
        active_ep.closed_at = now
        active_ep.closed_reason = "TIMEOUT"
        return active_ep

    if _should_close_by_green_streak(int(active_ep.green_streak or 0), n=close_green_n):
        active_ep.end_ts = bucket_end
        active_ep.closed_at = now
        active_ep.closed_reason = "GREEN_STREAK"
        return active_ep

    return active_ep
