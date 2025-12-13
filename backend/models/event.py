from datetime import datetime
from pydantic import BaseModel, Field


class Event(BaseModel):
    source: str = Field(..., examples=["home_assistant"])
    type: str = Field(..., examples=["motion", "door", "power"])
    value: str | None = Field(default=None, examples=["on", "off", "open", "closed"])
    timestamp: datetime
