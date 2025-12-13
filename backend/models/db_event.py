from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class EventDB(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    type = Column(String, nullable=False)
    value = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False)
