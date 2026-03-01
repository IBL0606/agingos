# schemas/anomaly_episode_persisted.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


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
    # MVP_FILL_REASONS_FROM_LAST: expose explainability in /v1/anomalies
    reasons_last: list[dict] | None = Field(default=None, exclude=True)
    reasons_peak: list[dict] | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _mvp_fill_reasons_from_last(self):
        # If persisted 'reasons' is empty, fall back to last/peak reasons.
        if not getattr(self, "reasons", None):
            rl = getattr(self, "reasons_last", None)
            rp = getattr(self, "reasons_peak", None)
            if rl:
                self.reasons = rl
            elif rp:
                self.reasons = rp
        return self

    human_weight_mode: str = "human_weighted"
    pet_weight: float = 0.25
    baseline_ref: Dict[str, Any] = Field(default_factory=dict)
