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
    def _normalize_id(cls, v: str) -> str:
        # Accept UUID, ULID, or any non-empty string.
        # Home Assistant may send non-UUID/ULID ids depending on template/rest_command usage.
        v = str(v).strip()
        if not v:
            raise ValueError("id must be a non-empty string")

        # UUID? (normalize to canonical form)
        try:
            return str(uuid.UUID(v))
        except Exception:
            pass

        # ULID? (Home Assistant context.id)
        if _ULID_RE.match(v):
            return v

        # Fallback: accept as-is
        return v

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_utc(cls, v: datetime) -> datetime:
        return require_utc_aware(v, field_name="timestamp")
