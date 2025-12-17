import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON, Text, Index
from db import Base


class DeviationV1Status(str, enum.Enum):
    OPEN = "OPEN"
    ACK = "ACK"
    CLOSED = "CLOSED"


class DeviationV1DB(Base):
    __tablename__ = "deviations_v1"

    id = Column(Integer, primary_key=True)

    deviation_id = Column(String(36), nullable=False, unique=True)

    deviation_key = Column(String(300), nullable=False, unique=True)
    rule_id = Column(String(20), nullable=False, index=True)
    subject_key = Column(String(200), nullable=False, index=True, default="default")

    status = Column(Enum(DeviationV1Status, name="deviation_v1_status"), nullable=False, default=DeviationV1Status.OPEN)

    severity = Column(String(10), nullable=False)  # "LOW" / "MEDIUM" / "HIGH"
    title = Column(String(200), nullable=False)
    explanation = Column(Text, nullable=False)

    evidence = Column(JSON, nullable=False, default=list)  # list[str] of event_id
    window_since = Column(DateTime, nullable=False)
    window_until = Column(DateTime, nullable=False)

    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


Index("ix_devv1_status_last_seen", DeviationV1DB.status, DeviationV1DB.last_seen_at)
Index("ix_devv1_rule_subject_status", DeviationV1DB.rule_id, DeviationV1DB.subject_key, DeviationV1DB.status)
