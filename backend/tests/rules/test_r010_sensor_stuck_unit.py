from __future__ import annotations

from datetime import datetime, timezone, timedelta

from services.rules.context import RuleContext
from services.rules.r010 import eval_r010_sensor_stuck_room_stuck


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

    def first(self):
        if not self._rows:
            return None
        return max(self._rows, key=lambda r: getattr(r, "timestamp", 0))


class _DB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *a, **k):
        return _Q(self._rows)


def _ctx(rows, now, params=None):
    since = now - timedelta(hours=24)
    until = now
    return RuleContext(
        session=_DB(rows), since=since, until=until, now=now, params=params or {}
    )


def test_r010_no_trigger_when_on_is_recent():
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    # presence on 30 minutes ago, stuck_minutes=240 => not stuck
    rows = [
        _Event(
            now - timedelta(minutes=30),
            "p1",
            "presence",
            {"room_id": "baderom", "state": "on"},
        ),
        # keep ingest live so liveness gate does not suppress
        _Event(now - timedelta(minutes=1), "h1", "heartbeat", {"state": "ok"}),
    ]

    devs = eval_r010_sensor_stuck_room_stuck(
        _ctx(rows, now, params={"stuck_minutes": 240, "lookback_minutes": 400})
    )
    assert devs == []


def test_r010_triggers_low_for_livingroom_stuck():
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    # presence on 300 minutes ago in stue, no off after -> stuck, severity LOW
    on_ts = now - timedelta(minutes=300)
    rows = [
        _Event(on_ts, "p1", "presence", {"room_id": "stue", "state": "on"}),
        _Event(now - timedelta(minutes=1), "h1", "heartbeat", {"state": "ok"}),
    ]

    devs = eval_r010_sensor_stuck_room_stuck(
        _ctx(rows, now, params={"stuck_minutes": 240, "lookback_minutes": 500})
    )
    assert len(devs) == 1
    assert devs[0].rule_id == "R-010"
    assert devs[0].severity == "LOW"
    assert "stue" in devs[0].evidence["stuck_rooms"]


def test_r010_triggers_medium_if_bathroom_stuck_present():
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    rows = [
        _Event(
            now - timedelta(minutes=300),
            "p1",
            "presence",
            {"room_id": "stue", "state": "on"},
        ),
        _Event(
            now - timedelta(minutes=300),
            "p2",
            "presence",
            {"room_id": "baderom", "state": "on"},
        ),
        _Event(now - timedelta(minutes=1), "h1", "heartbeat", {"state": "ok"}),
    ]

    devs = eval_r010_sensor_stuck_room_stuck(
        _ctx(rows, now, params={"stuck_minutes": 240, "lookback_minutes": 500})
    )
    assert len(devs) == 1
    assert devs[0].severity == "MEDIUM"
    assert set(devs[0].evidence["stuck_rooms"]) == {"baderom", "stue"}


def test_r010_no_trigger_if_off_exists_after_on():
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    on_ts = now - timedelta(minutes=300)
    rows = [
        _Event(on_ts, "p1", "presence", {"room_id": "baderom", "state": "on"}),
        _Event(
            on_ts + timedelta(minutes=5),
            "p2",
            "presence",
            {"room_id": "baderom", "state": "off"},
        ),
        _Event(now - timedelta(minutes=1), "h1", "heartbeat", {"state": "ok"}),
    ]

    devs = eval_r010_sensor_stuck_room_stuck(
        _ctx(rows, now, params={"stuck_minutes": 240, "lookback_minutes": 500})
    )
    assert devs == []
