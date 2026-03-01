from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Window(BaseModel):
    since: Optional[datetime] = None
    until: Optional[datetime] = None


EvidenceV1 = Union[List[str], Dict[str, Any]]


class DeviationV1(BaseModel):
    deviation_id: UUID = Field(default_factory=uuid4)
    rule_id: str
    timestamp: datetime
    severity: str
    title: str
    explanation: str
    # Back-compat: legacy evidence is List[str] (event_ids).
    # v1: dict with event_ids + structured fields.
    evidence: EvidenceV1 = Field(default_factory=list)
    window: Window
