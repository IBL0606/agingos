# models/event.py
from datetime import datetime
from typing import Any, Dict
import re
import uuid

from pydantic import BaseModel, Field, field_validator

from util.time import require_utc_aware

_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


class Event(BaseModel):
    id: str
    timestamp: datetime
    category: str
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _id_must_be_uuid_or_ulid(cls, v: str) -> str:
        # UUID?
        try:
            uuid.UUID(v)
            return v
        except Exception:
            pass

        # ULID? (Home Assistant context.id)
        if _ULID_RE.match(v):
            return v

        raise ValueError("id must be a valid UUID or ULID")

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_utc(cls, v: datetime) -> datetime:
        return require_utc_aware(v, field_name="timestamp")
