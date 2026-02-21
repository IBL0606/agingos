from __future__ import annotations

from datetime import datetime, timezone, timedelta

from services.rules.r002 import eval_r002_front_door_open_at_night


class _Row:
    def __init__(self, id: int, timestamp: datetime, payload: dict):
        self.id = id
        self.timestamp = timestamp
        self.payload = payload


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
    def filter(self, *args, **kwargs):
        return self
    def order_by(self, *args, **kwargs):
        return self
    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
    def query(self, *args, **kwargs):
        return _FakeQuery(self._rows)


def test_r002_triggers_on_door_open_at_night_default_window():
    # Default night window is 23:00 -> 06:00 (rule defaults if config params are missing)
    now = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=6)
    until = now

    night_ts = datetime(2026, 2, 21, 23, 30, 0, tzinfo=timezone.utc)
    rows = [_Row(123, night_ts, {"state": "open"})]

    devs = eval_r002_front_door_open_at_night(_FakeSession(rows), since=since, until=until, now=now)

    assert len(devs) == 1
    d = devs[0]
    assert d.rule_id == "R-002"
    assert d.severity == "HIGH"
    assert d.window.since == since
    assert d.window.until == until
    assert d.evidence == ["123"]


def test_r002_does_not_trigger_outside_night_window():
    now = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=6)
    until = now

    day_ts = datetime(2026, 2, 21, 12, 0, 0, tzinfo=timezone.utc)
    rows = [_Row(124, day_ts, {"state": "open"})]

    devs = eval_r002_front_door_open_at_night(_FakeSession(rows), since=since, until=until, now=now)

    assert devs == []
