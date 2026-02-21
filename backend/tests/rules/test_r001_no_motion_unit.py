from __future__ import annotations

from datetime import datetime, timezone, timedelta

from services.rules.r001 import eval_r001_no_motion


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self
    def order_by(self, *args, **kwargs):
        return self
    def all(self):
        return []


class _FakeSession:
    def query(self, *args, **kwargs):
        return _FakeQuery()


def test_r001_no_motion_returns_deviation_when_no_rows():
    now = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=3)
    until = now

    devs = eval_r001_no_motion(_FakeSession(), since=since, until=until, now=now)

    assert len(devs) == 1
    d = devs[0]
    assert d.rule_id == "R-001"
    assert d.severity == "MEDIUM"
    assert d.timestamp == now
    assert d.window.since == since
    assert d.window.until == until
    assert d.evidence == []

class _Row:
    def __init__(self, payload):
        self.payload = payload

class _FakeQueryRows(_FakeQuery):
    def __init__(self, rows):
        self._rows = rows
    def all(self):
        return self._rows

class _FakeSessionRows(_FakeSession):
    def __init__(self, rows):
        self._rows = rows
    def query(self, *args, **kwargs):
        return _FakeQueryRows(self._rows)

def test_r001_ignores_inactive_motion_payload():
    # One event in window, but payload indicates inactive (state != "on") -> should still trigger deviation
    now = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=3)
    until = now

    rows = [_Row({"state": "off"})]
    devs = eval_r001_no_motion(_FakeSessionRows(rows), since=since, until=until, now=now)

    assert len(devs) == 1
    assert devs[0].rule_id == "R-001"
