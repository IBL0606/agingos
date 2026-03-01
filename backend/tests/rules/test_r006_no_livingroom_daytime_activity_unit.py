from __future__ import annotations

from datetime import datetime, timezone, timedelta

from services.rules.context import RuleContext
from services.rules.r006 import eval_r006_no_livingroom_daytime_activity


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


def _ctx(rows, now, params=None):
    since = now - timedelta(hours=12)
    until = now
    return RuleContext(
        session=_DB(rows), since=since, until=until, now=now, params=params or {}
    )


def test_r006_triggers_when_no_livingroom_presence():
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    # No events at all -> should trigger (no livingroom presence)
    devs = eval_r006_no_livingroom_daytime_activity(_ctx([], now, params={"tz": "UTC"}))
    assert len(devs) == 1
    assert devs[0].rule_id == "R-006"


def test_r006_no_trigger_when_livingroom_presence_on_exists():
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    rows = [
        _Event(
            now - timedelta(hours=1),
            "e1",
            "presence",
            {"room_id": "stue", "state": "on"},
        )
    ]
    devs = eval_r006_no_livingroom_daytime_activity(
        _ctx(rows, now, params={"tz": "UTC"})
    )
    assert devs == []


def test_r006_suppressed_when_door_seen_and_other_presence():
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    rows = [
        _Event(now - timedelta(hours=2), "d1", "door", {"room_id": "inngang"}),
        _Event(
            now - timedelta(hours=1),
            "p1",
            "presence",
            {"room_id": "kjokken", "state": "on"},
        ),
    ]
    devs = eval_r006_no_livingroom_daytime_activity(
        _ctx(
            rows,
            now,
            params={
                "tz": "UTC",
                "living_room_id": "stue",
                "front_door_room_id": "inngang",
            },
        )
    )
    assert devs == []
