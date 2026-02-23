from __future__ import annotations

from datetime import datetime, timezone, timedelta

from services.rules.context import RuleContext
from services.rules.r004 import eval_r004_prolonged_bathroom_presence


class _Event:
    def __init__(self, ts, event_id, category, payload):
        self.timestamp = ts
        self.event_id = event_id
        self.category = category
        self.payload = payload


class _Q:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        return self._rows


class _DB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *a, **k):
        return _Q(self._rows)


def _ctx(rows, since, until, now, params=None):
    return RuleContext(session=_DB(rows), since=since, until=until, now=now, params=params or {})


def test_r004_no_events():
    now = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=2)
    until = now
    devs = eval_r004_prolonged_bathroom_presence(_ctx([], since, until, now))
    assert devs == []


def test_r004_day_segment_triggers_medium():
    now = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=3)
    until = now
    t_on = since + timedelta(minutes=0)
    t_off = since + timedelta(minutes=60)
    rows = [
        _Event(t_on, "e1", "presence", {"room_id": "baderom", "state": "on"}),
        _Event(t_off, "e2", "presence", {"room_id": "baderom", "state": "off"}),
    ]
    devs = eval_r004_prolonged_bathroom_presence(_ctx(rows, since, until, now, params={"tz": "UTC"}))
    assert len(devs) == 1
    assert devs[0].severity in ("MEDIUM", "HIGH")


def test_r004_night_boost_triggers_high():
    now = datetime(2026, 2, 22, 23, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=1)
    until = now
    t_on = since + timedelta(minutes=0)
    t_off = since + timedelta(minutes=30)
    rows = [
        _Event(t_on, "e1", "presence", {"room_id": "baderom", "state": "on"}),
        _Event(t_off, "e2", "presence", {"room_id": "baderom", "state": "off"}),
    ]
    params = {"tz": "UTC", "night_threshold_min": 25, "day_threshold_min": 45, "night_start_hour": 22, "night_end_hour": 7}
    devs = eval_r004_prolonged_bathroom_presence(_ctx(rows, since, until, now, params=params))
    assert len(devs) == 1
    assert devs[0].severity == "HIGH"


def test_r004_stuck_protection_sets_low_sensor_fault():
    now = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=6)
    until = now
    t_on = since + timedelta(minutes=0)
    rows = [
        _Event(t_on, "e1", "presence", {"room_id": "baderom", "state": "on"}),
    ]
    params = {"tz": "UTC", "sensor_stuck_min": 240}
    devs = eval_r004_prolonged_bathroom_presence(_ctx(rows, since, until, now, params=params))
    assert len(devs) == 1
    assert devs[0].severity == "LOW"
    assert isinstance(devs[0].evidence, dict)
    assert devs[0].evidence.get("sensor_fault") is True
