from __future__ import annotations

from datetime import datetime, timezone, timedelta

from services.rules.context import RuleContext
from services.rules.r005 import eval_r005_no_bathroom_activity_24h


class _Event:
    def __init__(self, ts, category, payload, event_id="e"):
        self.timestamp = ts
        self.category = category
        self.payload = payload
        self.event_id = event_id


class _Q:
    def __init__(self, rows, first_row=None):
        self._rows = rows
        self._first = first_row

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._first


class _DB:
    """
    Supports:
      - R-009 liveness: query(...).order_by(...).filter(...).first()
      - R-005 bathroom scan: query(...).filter(...).order_by(...).all()
    """

    def __init__(self, rows_for_all, last_event_ts=None):
        self._rows_for_all = rows_for_all
        self._last_event_ts = last_event_ts

    def query(self, *a, **k):
        first_row = None
        if self._last_event_ts is not None:
            first_row = _Event(
                self._last_event_ts,
                "presence",
                {"room_id": "stue", "state": "on"},
                event_id="last",
            )
        return _Q(self._rows_for_all, first_row=first_row)


def _ctx(db, since, until, now, params=None):
    return RuleContext(
        session=db, since=since, until=until, now=now, params=params or {}
    )


def test_r005_triggers_when_no_bathroom_activity_and_ingest_ok():
    now = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=1)
    until = now

    db = _DB(rows_for_all=[], last_event_ts=now - timedelta(minutes=5))  # ingest ok
    devs = eval_r005_no_bathroom_activity_24h(
        _ctx(db, since, until, now, params={"lookback_hours": 24})
    )
    assert len(devs) == 1
    assert devs[0].rule_id == "R-005"
    assert devs[0].severity == "LOW"


def test_r005_no_trigger_when_bathroom_presence_on_exists():
    now = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=1)
    until = now

    rows = [
        _Event(
            now - timedelta(hours=2),
            "presence",
            {"room_id": "baderom", "state": "on"},
            event_id="b1",
        )
    ]
    db = _DB(rows_for_all=rows, last_event_ts=now - timedelta(minutes=5))  # ingest ok

    devs = eval_r005_no_bathroom_activity_24h(
        _ctx(db, since, until, now, params={"lookback_hours": 24})
    )
    assert devs == []


def test_r005_suppressed_when_ingest_stopped():
    now = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=1)
    until = now

    db = _DB(
        rows_for_all=[], last_event_ts=now - timedelta(minutes=40)
    )  # ingest stopped
    devs = eval_r005_no_bathroom_activity_24h(
        _ctx(
            db,
            since,
            until,
            now,
            params={"lookback_hours": 24, "liveness_max_age_minutes": 15},
        )
    )
    assert devs == []
