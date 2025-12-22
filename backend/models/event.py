# models/event.py
from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from util.time import require_utc_aware


class Event(BaseModel):
    id: UUID
    timestamp: datetime
    category: str
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_utc(cls, v: datetime) -> datetime:
        return require_utc_aware(v, field_name="timestamp")
