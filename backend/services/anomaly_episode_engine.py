# services/anomaly_episode_engine.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date
from typing import Optional, Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.anomaly_episode import AnomalyLevel
from services.anomalies_repo import create_episode, update_episode_peak, close_episode
from services.anomaly_scoring import BucketScore


def _level_int(level: str) -> int:
    s = (level or "").strip().upper()
    return {"GREEN": AnomalyLevel.GREEN, "YELLOW": AnomalyLevel.YELLOW, "RED": AnomalyLevel.RED}.get(s, AnomalyLevel.GREEN)


def _choose_episode_level(current_level_i: int, new_level_i: int) -> int:
    # episode level = max severity seen
    return max(int(current_level_i), int(new_level_i))


@dataclass
class EpisodeProcessResult:
    action: str  # "noop"|"opened"|"updated"|"closed"
    episode_id: Optional[int]
    episode_active: bool


def _get_active_episode(db: Session, room: str) -> Optional[dict]:
    row = db.execute(
        text(
            """
            SELECT id, level, score_total, peak_bucket_score, start_ts, end_ts
            FROM anomaly_episodes
            WHERE room = :room AND end_ts IS NULL
            ORDER BY start_ts DESC
            LIMIT 1
            """
        ),
        {"room": room},
    ).mappings().first()
    return dict(row) if row else None



def _json_safe(x: Any) -> Any:
    """Recursively convert non-JSON-serializable types (date/datetime) into ISO strings."""
    if x is None:
        return None
    if isinstance(x, (datetime, date)):
        return x.isoformat()
    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_safe(v) for v in x]
    return x

def process_bucket_score(
    db: Session,
    *,
    bucket: BucketScore,
    close_after_green_buckets: int = 2,
) -> EpisodeProcessResult:
    """
    Debounce rules (deterministic):
    - Only YELLOW/RED creates/extends an episode.
    - Episode stays open until we have N consecutive GREEN buckets after last non-green.
    - Peak bucket tracked by max score_total; store peak_bucket_details = bucket.details
    - reasons stored from peak bucket (not appended), to keep explainability consistent.
    """
    room = bucket.room
    level_i = _level_int(bucket.level)

    active = _get_active_episode(db, room)

    # Helper: track consecutive green buckets using anomaly_episodes.peak_bucket_details['green_streak'] (lightweight).
    def _get_green_streak(ep_details: Optional[dict]) -> int:
        if not isinstance(ep_details, dict):
            return 0
        return int(ep_details.get("green_streak") or 0)

    def _set_green_streak(ep_details: Optional[dict], streak: int) -> dict:
        d = dict(ep_details or {})
        d["green_streak"] = int(streak)
        return d

    if not active:
        # No open episode
        if level_i <= AnomalyLevel.GREEN:
            return EpisodeProcessResult(action="noop", episode_id=None, episode_active=False)

        # Open new episode
        ep = create_episode(
            db,
            room=room,
            start_ts=bucket.bucket_start,
            level=level_i,
            score_total=bucket.score_total,
            score_intensity=bucket.score_intensity,
            score_sequence=bucket.score_sequence,
            score_event=bucket.score_event,
            peak_bucket_start_ts=bucket.bucket_start,
            peak_bucket_score=bucket.score_total,
            reasons=_json_safe(bucket.reasons),
            peak_bucket_details=_json_safe(_set_green_streak(bucket.details, 0)),
            human_weight_mode="human_weighted",
            pet_weight=float(bucket.details.get("observed", {}).get("pet_weight") or 0.25),
            baseline_ref={"model_end": (str(bucket.details.get("model_end")) if bucket.details.get("model_end") is not None else None), "window_days": 7, "bucket_minutes": 15, "baseline_version": "v1"},
        )
        return EpisodeProcessResult(action="opened", episode_id=ep.id, episode_active=True)

    # There is an active episode
    ep_id = int(active["id"])

    # GREEN bucket while episode active: increment streak, close if threshold reached
    if level_i <= AnomalyLevel.GREEN:
        # fetch current peak_bucket_details for streak
        row = db.execute(
            text("SELECT peak_bucket_details FROM anomaly_episodes WHERE id = :id"),
            {"id": ep_id},
        ).mappings().first()
        cur_details = row["peak_bucket_details"] if row else None
        streak = _get_green_streak(cur_details) + 1

        if streak >= close_after_green_buckets:
            close_episode(db, episode_id=ep_id, end_ts=bucket.bucket_end)
            return EpisodeProcessResult(action="closed", episode_id=ep_id, episode_active=False)

        # keep episode open; just update updated_at and streak (no score changes)
        db.execute(
            text(
                """
                UPDATE anomaly_episodes
                SET updated_at = now(),
                    peak_bucket_details = :details
                WHERE id = :id
                """
            ),
            {"id": ep_id, "details": _set_green_streak(cur_details, streak)},
        )
        db.commit()
        return EpisodeProcessResult(action="updated", episode_id=ep_id, episode_active=True)

    # Non-green: reset green streak and update peak if this bucket is higher
    row = db.execute(
        text(
            "SELECT level, score_total, peak_bucket_score, peak_bucket_details FROM anomaly_episodes WHERE id = :id"
        ),
        {"id": ep_id},
    ).mappings().first()
    if not row:
        return EpisodeProcessResult(action="noop", episode_id=ep_id, episode_active=True)

    cur_level_i = int(row["level"] or 0)
    cur_peak = row["peak_bucket_score"]
    cur_peak = float(cur_peak) if cur_peak is not None else None
    cur_details = row["peak_bucket_details"]

    # reset streak
    new_details = _set_green_streak(cur_details, 0)

    new_level_i = _choose_episode_level(cur_level_i, level_i)

    # update peak if this is higher
    if cur_peak is None or bucket.score_total >= cur_peak:
        update_episode_peak(
            db,
            episode_id=ep_id,
            level=new_level_i,
            score_total=bucket.score_total,
            score_intensity=bucket.score_intensity,
            score_sequence=bucket.score_sequence,
            score_event=bucket.score_event,
            peak_bucket_start_ts=bucket.bucket_start,
            peak_bucket_score=bucket.score_total,
            reasons=_json_safe(bucket.reasons),
            peak_bucket_details=_json_safe(_set_green_streak(bucket.details, 0)),
        )
        return EpisodeProcessResult(action="updated", episode_id=ep_id, episode_active=True)

    # Not a new peak: only bump level + reset streak details
    db.execute(
        text(
            """
            UPDATE anomaly_episodes
            SET updated_at = now(),
                level = :level,
                peak_bucket_details = :details
            WHERE id = :id
            """
        ),
        {"id": ep_id, "level": new_level_i, "details": new_details},
    )
    db.commit()
    return EpisodeProcessResult(action="updated", episode_id=ep_id, episode_active=True)
