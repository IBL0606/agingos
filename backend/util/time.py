from __future__ import annotations

from datetime import datetime, timezone


class TimePolicyError(ValueError):
    pass


def require_utc_aware(dt: datetime, field_name: str) -> datetime:
    """
    Strict policy:
    - dt MUST be timezone-aware
    - converted to UTC
    """
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise TimePolicyError(
            f"{field_name} must be timezone-aware UTC (ISO 8601, e.g. 2025-01-01T00:00:00Z)"
        )
    return dt.astimezone(timezone.utc)


def utcnow() -> datetime:
    """Returns timezone-aware UTC now (used for now-injection in tests)."""
    return datetime.now(timezone.utc)
