# models/anomaly_episode.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, Index, SmallInteger, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.db_event import Base
from util.time import utcnow


class AnomalyLevel:
    GREEN = 0
    YELLOW = 1
    RED = 2


class AnomalyEpisode(Base):
    __tablename__ = "anomaly_episodes"

    id: Mapped[int] = mapped_column(primary_key=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    room: Mapped[str] = mapped_column(Text, nullable=False)

    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_ts: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # 0=GREEN, 1=YELLOW, 2=RED
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    score_total: Mapped[float] = mapped_column(Float, nullable=False)
    score_intensity: Mapped[float] = mapped_column(Float, nullable=False)
    score_sequence: Mapped[float] = mapped_column(Float, nullable=False)
    score_event: Mapped[float] = mapped_column(Float, nullable=False)

    peak_bucket_start_ts: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    peak_bucket_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # reasons: [{reason_code, component, points, evidence}]
    reasons: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    # Optional evidence snapshot for the peak bucket
    peak_bucket_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    human_weight_mode: Mapped[str] = mapped_column(Text, nullable=False, default="human_weighted")
    pet_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.25)

    baseline_ref: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)



    # Lifecycle fields (episode engine)
    start_bucket: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_bucket: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    peak_bucket: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    peak_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_level: Mapped[str | None] = mapped_column(Text, nullable=True)

    green_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bucket_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    reasons_peak: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    reasons_last: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
Index("ix_anomaly_episodes_start_ts", AnomalyEpisode.start_ts)
Index("ix_anomaly_episodes_room_start_ts", AnomalyEpisode.room, AnomalyEpisode.start_ts)
Index("ix_anomaly_episodes_end_ts", AnomalyEpisode.end_ts)
