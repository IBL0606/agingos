from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime


class Window(BaseModel):
    since: Optional[datetime] = None
    until: Optional[datetime] = None
class DeviationV1(BaseModel):
    deviation_id: UUID = Field(default_factory=uuid4)
    rule_id: str
    timestamp: datetime
    severity: str
    title: str
    explanation: str
    evidence: List[str] = Field(default_factory=list)
    window: Window
