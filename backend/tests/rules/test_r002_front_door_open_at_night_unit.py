from __future__ import annotations

from datetime import datetime, timezone, timedelta

from services.rules.context import RuleContext
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


def test_r002_triggers_on_local_night_default_window_europe_oslo():
    now = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=12)
    until = now

    # 2026-02-20 22:30 UTC == 23:30 local (Europe/Oslo, UTC+1)
    night_local_ts_utc = datetime(2026, 2, 20, 22, 30, 0, tzinfo=timezone.utc)
    rows = [_Row(123, night_local_ts_utc, {"state": "open"})]

    ctx = RuleContext(
        session=_FakeSession(rows), since=since, until=until, now=now, params={}
    )
    devs = eval_r002_front_door_open_at_night(ctx)

    assert len(devs) == 1
    d = devs[0]
    assert d.rule_id == "R-002"
    assert d.severity == "HIGH"
    assert d.window.since == since
    assert d.window.until == until
    assert d.evidence == ["123"]


def test_r002_does_not_trigger_on_local_daytime_default_window_europe_oslo():
    now = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=12)
    until = now

    # 2026-02-21 11:00 UTC == 12:00 local (Europe/Oslo, UTC+1)
    day_local_ts_utc = datetime(2026, 2, 21, 11, 0, 0, tzinfo=timezone.utc)
    rows = [_Row(124, day_local_ts_utc, {"state": "open"})]

    ctx = RuleContext(
        session=_FakeSession(rows), since=since, until=until, now=now, params={}
    )
    devs = eval_r002_front_door_open_at_night(ctx)

    assert devs == []


def test_r002_regression_march_0555utc_is_not_night_in_oslo_default_window():
    now = datetime(2026, 3, 10, 8, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=6)
    until = now

    # 2026-03-10 05:55 UTC == 06:55 local (Europe/Oslo, UTC+1 before DST switch)
    near_pilot_ts_utc = datetime(2026, 3, 10, 5, 55, 0, tzinfo=timezone.utc)
    rows = [_Row(125, near_pilot_ts_utc, {"state": "open"})]

    ctx = RuleContext(
        session=_FakeSession(rows), since=since, until=until, now=now, params={}
    )
    devs = eval_r002_front_door_open_at_night(ctx)

    assert devs == []
