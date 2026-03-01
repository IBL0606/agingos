from __future__ import annotations

from datetime import datetime, timezone, timedelta

from services.rules.context import RuleContext
from services.rules.r003 import eval_r003_front_door_open_no_motion_after


class _Row:
    def __init__(self, id: int, timestamp: datetime, category: str, payload: dict):
        self.id = id
        self.timestamp = timestamp
        self.category = category
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


def test_r003_triggers_when_front_door_open_and_no_motion_in_followup():
    now = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=6)
    until = now

    door_ts = datetime(2026, 2, 21, 9, 0, 0, tzinfo=timezone.utc)
    # Door matches defaults: door_category="door", door_open_value="open", required_door_name="front"
    rows = [
        _Row(210, door_ts, "door", {"state": "open", "door": "front"}),
        # No motion rows in followup window => trigger
    ]

    ctx = RuleContext(
        session=_FakeSession(rows), since=since, until=until, now=now, params={}
    )
    devs = eval_r003_front_door_open_no_motion_after(ctx)

    assert len(devs) == 1
    assert devs[0].rule_id == "R-003"
    assert devs[0].evidence == ["210"]


def test_r003_does_not_trigger_when_motion_in_followup_window():
    now = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=6)
    until = now

    door_ts = datetime(2026, 2, 21, 9, 0, 0, tzinfo=timezone.utc)
    motion_ts = door_ts + timedelta(minutes=5)

    rows = [
        _Row(211, door_ts, "door", {"state": "open", "door": "front"}),
        _Row(212, motion_ts, "motion", {"state": "on"}),
    ]

    ctx = RuleContext(
        session=_FakeSession(rows), since=since, until=until, now=now, params={}
    )
    devs = eval_r003_front_door_open_no_motion_after(ctx)

    assert devs == []
