# models/event.py
from pydantic import BaseModel, Field
from typing import Any, Dict
from uuid import UUID
from datetime import datetime


class Event(BaseModel):
    id: UUID
    timestamp: datetime
    category: str
    payload: Dict[str, Any] = Field(default_factory=dict)
