from pydantic import BaseModel
from typing import List
from uuid import UUID
from datetime import datetime


class Window(BaseModel):
    since: datetime
    until: datetime


class DeviationPersisted(BaseModel):
    deviation_id: int
    rule_id: str  # f.eks. "R-003"
    status: str   # "OPEN" / "ACK" / "CLOSED"
    severity: str # "LOW" / "MEDIUM" / "HIGH"

    title: str
    explanation: str

    timestamp: datetime  # tidspunkt avviket ble generert (fra context)
    started_at: datetime
    last_seen_at: datetime

    subject_key: str
    evidence: List[UUID] = []
    window: Window
