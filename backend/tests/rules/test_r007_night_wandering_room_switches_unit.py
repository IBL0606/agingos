from __future__ import annotations

from datetime import datetime, timezone, timedelta

from services.rules.context import RuleContext
from services.rules.r007 import eval_r007_night_wandering_room_switches


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


def test_r007_triggers_on_many_room_switches():
    now = datetime(2026, 2, 22, 23, 30, tzinfo=timezone.utc)
    base = now - timedelta(hours=1)
    # 6 switches: A->B->A->B->A->B->A (7 events)
    rooms = ["stue", "gang", "stue", "gang", "stue", "gang", "stue"]
    rows = []
    for i, room in enumerate(rooms):
        rows.append(
            _Event(
                base + timedelta(minutes=i),
                f"e{i}",
                "presence",
                {"room_id": room, "state": "on"},
            )
        )

    devs = eval_r007_night_wandering_room_switches(
        _ctx(rows, now, params={"tz": "UTC", "switch_threshold": 6})
    )
    assert len(devs) == 1
    assert devs[0].rule_id == "R-007"
    assert devs[0].severity == "MEDIUM"


def test_r007_door_boost_high():
    now = datetime(2026, 2, 22, 23, 30, tzinfo=timezone.utc)
    base = now - timedelta(hours=1)
    rooms = ["stue", "gang", "stue", "gang", "stue", "gang", "stue"]
    rows = []
    for i, room in enumerate(rooms):
        rows.append(
            _Event(
                base + timedelta(minutes=i),
                f"e{i}",
                "presence",
                {"room_id": room, "state": "on"},
            )
        )
    rows.append(
        _Event(base + timedelta(minutes=2), "d1", "door", {"room_id": "inngang"})
    )

    devs = eval_r007_night_wandering_room_switches(
        _ctx(
            rows,
            now,
            params={
                "tz": "UTC",
                "switch_threshold": 6,
                "front_door_room_id": "inngang",
            },
        )
    )
    assert len(devs) == 1
    assert devs[0].severity == "HIGH"


def test_r007_no_trigger_when_switches_below_threshold():
    now = datetime(2026, 2, 22, 23, 30, tzinfo=timezone.utc)
    base = now - timedelta(hours=1)
    rooms = ["stue", "gang", "stue"]  # only 2 switches
    rows = []
    for i, room in enumerate(rooms):
        rows.append(
            _Event(
                base + timedelta(minutes=i),
                f"e{i}",
                "presence",
                {"room_id": room, "state": "on"},
            )
        )

    devs = eval_r007_night_wandering_room_switches(
        _ctx(rows, now, params={"tz": "UTC", "switch_threshold": 6})
    )
    assert devs == []
