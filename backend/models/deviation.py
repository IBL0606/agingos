#models/deviation.py
import enum
from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from util.time import utcnow
from models.db_event import Base

class DeviationStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACK = "ACK"
    CLOSED = "CLOSED"

class Deviation(Base):
    __tablename__ = "deviations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    rule_id: Mapped[int] = mapped_column(
        ForeignKey("rules.id"),
        nullable=False
    )

    status: Mapped[DeviationStatus] = mapped_column(
        Enum(DeviationStatus, name="deviation_status"),
        nullable=False,
        default=DeviationStatus.OPEN
    )

    severity: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow
    )

    subject_key: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="default"
    )

    context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


Index(
    "ix_deviations_status_last_seen",
    Deviation.status,
    Deviation.last_seen_at
)

Index(
    "uq_deviations_active_rule_subject",
    Deviation.rule_id,
    Deviation.subject_key,
    unique=True,
    postgresql_where=Deviation.status.in_([DeviationStatus.OPEN, DeviationStatus.ACK]),
)

