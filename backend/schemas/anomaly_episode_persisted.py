# schemas/anomaly_episode_persisted.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnomalyEpisodePersisted(BaseModel):
    id: int = Field(..., description="Episode id")
    room: str

    start_ts: datetime
    end_ts: Optional[datetime] = None
    active: bool

    level: str  # GREEN|YELLOW|RED

    score_total: float
    score_intensity: float
    score_sequence: float
    score_event: float

    peak_bucket_start_ts: Optional[datetime] = None
    peak_bucket_score: Optional[float] = None

    reasons: List[Dict[str, Any]] = Field(default_factory=list)

    human_weight_mode: str = "human_weighted"
    pet_weight: float = 0.25
    baseline_ref: Dict[str, Any] = Field(default_factory=dict)
