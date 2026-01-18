from pydantic import BaseModel, Field
from typing import List
from uuid import UUID, uuid4
from datetime import datetime


class Window(BaseModel):
    since: datetime
    until: datetime


class DeviationV1(BaseModel):
    deviation_id: UUID = Field(default_factory=uuid4)
    rule_id: str
    timestamp: datetime
    severity: str
    title: str
    explanation: str
    evidence: List[str] = []
    window: Window
