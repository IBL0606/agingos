# models/db_event.py
from sqlalchemy import Column, Integer, String, DateTime, JSON, Index, text
from db import Base


class EventDB(Base):
    __tablename__ = "events"

    __table_args__ = (
        Index("ix_events_event_id", "event_id"),
        Index("ix_events_timestamp", "timestamp"),
        Index("ix_events_category", "category"),
    )

    id = Column(Integer, primary_key=True)
    event_id = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    category = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    org_id = Column(String, nullable=False)
    home_id = Column(String, nullable=False)
    subject_id = Column(String, nullable=False)
    stream_id = Column(String, nullable=False, server_default=text("'prod'"))
