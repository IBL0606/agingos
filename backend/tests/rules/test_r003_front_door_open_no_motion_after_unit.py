from __future__ import annotations

from datetime import datetime, timezone, timedelta

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
        # We deliberately ignore SQLAlchemy filter expressions in unit tests.
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    """
    Returns different row sets depending on which query is being asked:
      - door query: returns door_rows
      - motion query: returns motion_rows
    """
    def __init__(self, door_rows, motion_rows):
        self._door_rows = door_rows
        self._motion_rows = motion_rows
        self._q = 0

    def query(self, *args, **kwargs):
        self._q += 1
        # First query in rule is door_rows; subsequent query is motion_rows
        if self._q == 1:
            return _FakeQuery(self._door_rows)
        return _FakeQuery(self._motion_rows)


def test_r003_triggers_when_door_open_and_no_motion_in_followup():
    now = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=6)
    until = now

    door_ts = datetime(2026, 2, 21, 9, 0, 0, tzinfo=timezone.utc)
    door_rows = [_Row(200, door_ts, "door", {"state": "open", "door": "front"})]
    motion_rows = []  # no follow-up activity

    devs = eval_r003_front_door_open_no_motion_after(_FakeSession(door_rows, motion_rows), since=since, until=until, now=now)

    assert len(devs) == 1
    d = devs[0]
    assert d.rule_id == "R-003"
    assert d.severity == "MEDIUM"
    assert d.evidence == ["200"]
    assert d.window.since == since
    assert d.window.until == until


def test_r003_does_not_trigger_when_motion_present_in_followup():
    now = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=6)
    until = now

    door_ts = datetime(2026, 2, 21, 9, 0, 0, tzinfo=timezone.utc)
    door_rows = [_Row(201, door_ts, "door", {"state": "open", "door": "front"})]

    motion_ts = door_ts + timedelta(minutes=3)
    motion_rows = [_Row(300, motion_ts, "motion", {"state": "on"})]

    devs = eval_r003_front_door_open_no_motion_after(_FakeSession(door_rows, motion_rows), since=since, until=until, now=now)

    assert devs == []


def test_r003_does_not_trigger_for_other_door_name():
    now = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
    since = now - timedelta(hours=6)
    until = now

    door_ts = datetime(2026, 2, 21, 9, 0, 0, tzinfo=timezone.utc)
    # required_door_name default is "front"; here we use "back"
    door_rows = [_Row(202, door_ts, "door", {"state": "open", "door": "back"})]
    motion_rows = []

    devs = eval_r003_front_door_open_no_motion_after(_FakeSession(door_rows, motion_rows), since=since, until=until, now=now)

    assert devs == []
