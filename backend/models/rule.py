import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from util.time import utcnow_db
from models.db_event import Base

class RuleType(str, enum.Enum):
    NO_MOTION = "NO_MOTION"

class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    rule_type: Mapped[RuleType] = mapped_column(
        Enum(RuleType, name="rule_type"),
        nullable=False
    )

    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    severity: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow_db
    )
