# models/db_event.py
from sqlalchemy import Column, Integer, String, DateTime, JSON
from db import Base


class EventDB(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
