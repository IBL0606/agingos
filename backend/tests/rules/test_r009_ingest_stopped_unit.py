from __future__ import annotations

from datetime import datetime, timezone, timedelta

from services.rules.context import RuleContext
from services.rules.r009 import eval_r009_ingest_stopped


class _Event:
    def __init__(self, ts):
        self.timestamp = ts


class _Q:
    def __init__(self, rows):
        self._rows = rows

    def order_by(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _DB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *a, **k):
        return _Q(self._rows)


def _ctx(rows, since, until, now, params=None):
    return RuleContext(
        session=_DB(rows), since=since, until=until, now=now, params=params or {}
    )


def test_r009_no_events_triggers():
    now = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    since = now - timedelta(minutes=30)
    until = now
    devs = eval_r009_ingest_stopped(_ctx([], since, until, now))
    assert len(devs) == 1
    assert devs[0].rule_id == "R-009"
    assert devs[0].severity == "HIGH"


def test_r009_recent_event_no_trigger():
    now = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    since = now - timedelta(minutes=30)
    until = now
    last = now - timedelta(minutes=5)
    devs = eval_r009_ingest_stopped(
        _ctx([_Event(last)], since, until, now, params={"max_age_minutes": 15})
    )
    assert devs == []


def test_r009_old_event_triggers():
    now = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    since = now - timedelta(minutes=30)
    until = now
    last = now - timedelta(minutes=40)
    devs = eval_r009_ingest_stopped(
        _ctx([_Event(last)], since, until, now, params={"max_age_minutes": 15})
    )
    assert len(devs) == 1
