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


def to_db_utc_naive(dt: datetime, field_name: str) -> datetime:
    """
    Temporary adapter while DB columns are 'timestamp without time zone'.
    Stores UTC as naive datetime (tzinfo=None), but only after strict UTC validation.
    """
    dt_utc = require_utc_aware(dt, field_name=field_name)
    return dt_utc.replace(tzinfo=None)


def from_db_utc_naive(dt: datetime) -> datetime:
    """
    Interprets naive DB timestamps as UTC and returns timezone-aware UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
def utcnow_db() -> datetime:
    """
    Returns "now" as naive UTC for writing into DB columns that are
    'timestamp without time zone' (temporary until timestamptz migration).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
