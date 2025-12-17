from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from models.deviation_v1_db import DeviationV1DB, DeviationV1Status


@dataclass
class PersistResult:
    created: int = 0
    updated: int = 0
    reopened: int = 0


def _deviation_key(rule_id: str, subject_key: str) -> str:
    return f"{rule_id}:{subject_key}"


def _window_since(d) -> datetime:
    w = getattr(d, "window")
    return w["since"] if isinstance(w, dict) else w.since


def _window_until(d) -> datetime:
    w = getattr(d, "window")
    return w["until"] if isinstance(w, dict) else w.until


def upsert_deviations_v1(
    db: Session,
    deviations: list,
    subject_key: str,
    now: datetime,
) -> tuple[PersistResult, set[str]]:
    """
    Upsert policy:
      - key = rule_id + subject_key
      - create if missing
      - update if exists (CLOSED -> OPEN reopen)
      - ACK is preserved, but last_seen_at is updated
    Returns (result, seen_keys).
    """
    result = PersistResult()
    seen_keys: set[str] = set()

    for d in deviations:
        key = _deviation_key(d.rule_id, subject_key)
        seen_keys.add(key)

        row = db.query(DeviationV1DB).filter(DeviationV1DB.deviation_key == key).one_or_none()

        if row is None:
            row = DeviationV1DB(
                deviation_id=str(d.deviation_id),
                deviation_key=key,
                rule_id=d.rule_id,
                subject_key=subject_key,
                status=DeviationV1Status.OPEN,
                severity=str(d.severity),
                title=str(d.title),
                explanation=str(d.explanation),
                evidence=[str(x) for x in list(d.evidence)],
                window_since=_window_since(d),
                window_until=_window_until(d),
                first_seen_at=now,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            result.created += 1
            continue

        if row.status == DeviationV1Status.CLOSED:
            row.status = DeviationV1Status.OPEN
            row.closed_at = None
            result.reopened += 1

        # Update content and timestamps; keep ACK as ACK
        row.severity = str(d.severity)
        row.title = str(d.title)
        row.explanation = str(d.explanation)
        row.evidence = [str(x) for x in list(d.evidence)]
        row.window_since = _window_since(d)
        row.window_until = _window_until(d)
        row.last_seen_at = now
        row.updated_at = now

        result.updated += 1

    return result, seen_keys


def close_stale_deviations_v1(
    db: Session,
    subject_key: str,
    rule_ids: list[str],
    seen_keys: set[str],
    now: datetime,
    expire_after_minutes: int,
) -> int:
    """
    Minimum viable closing:
      - Close OPEN/ACK deviations for (rule_ids, subject_key)
      - Only if last_seen_at older than threshold AND not seen in this run
    """
    threshold = now - timedelta(minutes=expire_after_minutes)

    rows = (
        db.query(DeviationV1DB)
        .filter(DeviationV1DB.subject_key == subject_key)
        .filter(DeviationV1DB.rule_id.in_(rule_ids))
        .filter(DeviationV1DB.status.in_([DeviationV1Status.OPEN, DeviationV1Status.ACK]))
        .filter(DeviationV1DB.last_seen_at < threshold)
        .all()
    )

    to_close = [r for r in rows if r.deviation_key not in seen_keys]

    for r in to_close:
        r.status = DeviationV1Status.CLOSED
        r.closed_at = now
        r.updated_at = now

    return len(to_close)
