# services/anomalies_repo.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.anomaly_episode import AnomalyEpisode
from util.time import utcnow


def list_episodes(
    db: Session,
    *,
    since: datetime,
    room: Optional[str] = None,
    active_only: bool = False,
    limit: int = 200,
) -> list[AnomalyEpisode]:
    q = select(AnomalyEpisode).where(AnomalyEpisode.start_ts >= since)
    if room:
        q = q.where(AnomalyEpisode.room == room)
    if active_only:
        q = q.where(AnomalyEpisode.end_ts.is_(None))
    q = q.order_by(AnomalyEpisode.start_ts.desc())
    if limit:
        q = q.limit(limit)
    return list(db.execute(q).scalars().all())


def create_episode(
    db: Session,
    *,
    room: str,
    start_ts: datetime,
    level: int,
    score_total: float,
    score_intensity: float,
    score_sequence: float,
    score_event: float,
    peak_bucket_start_ts: Optional[datetime] = None,
    peak_bucket_score: Optional[float] = None,
    reasons: Optional[list[dict]] = None,
    peak_bucket_details: Optional[dict] = None,
    human_weight_mode: str = "human_weighted",
    pet_weight: float = 0.25,
    baseline_ref: Optional[dict] = None,
) -> AnomalyEpisode:
    ep = AnomalyEpisode(
        room=room,
        start_ts=start_ts,
        end_ts=None,
        level=level,
        score_total=score_total,
        score_intensity=score_intensity,
        score_sequence=score_sequence,
        score_event=score_event,
        peak_bucket_start_ts=peak_bucket_start_ts,
        peak_bucket_score=peak_bucket_score,
        reasons=reasons or [],
        peak_bucket_details=peak_bucket_details,
        human_weight_mode=human_weight_mode,
        pet_weight=pet_weight,
        baseline_ref=baseline_ref or {},
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def update_episode_peak(
    db: Session,
    *,
    episode_id: int,
    level: int,
    score_total: float,
    score_intensity: float,
    score_sequence: float,
    score_event: float,
    peak_bucket_start_ts: Optional[datetime],
    peak_bucket_score: Optional[float],
    reasons: list[dict],
    peak_bucket_details: Optional[dict],
) -> AnomalyEpisode:
    ep = db.get(AnomalyEpisode, episode_id)
    if not ep:
        raise KeyError(f"AnomalyEpisode {episode_id} not found")

    ep.level = level
    ep.score_total = score_total
    ep.score_intensity = score_intensity
    ep.score_sequence = score_sequence
    ep.score_event = score_event
    ep.peak_bucket_start_ts = peak_bucket_start_ts
    ep.peak_bucket_score = peak_bucket_score
    ep.reasons = reasons
    ep.peak_bucket_details = peak_bucket_details
    ep.updated_at = utcnow()

    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def close_episode(db: Session, *, episode_id: int, end_ts: datetime) -> AnomalyEpisode:
    ep = db.get(AnomalyEpisode, episode_id)
    if not ep:
        raise KeyError(f"AnomalyEpisode {episode_id} not found")
    ep.end_ts = end_ts
    ep.updated_at = utcnow()
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def parse_last_param_to_since(last: str) -> datetime:
    """
    Accepts '24h', '7d', '60m'. Defaults to 24h if invalid.
    """
    s = (last or "").strip().lower()
    now = datetime.now(timezone.utc)
    try:
        if s.endswith("h"):
            return now - timedelta(hours=float(s[:-1]))
        if s.endswith("d"):
            return now - timedelta(days=float(s[:-1]))
        if s.endswith("m"):
            return now - timedelta(minutes=float(s[:-1]))
    except Exception:
        pass
    return now - timedelta(hours=24)
