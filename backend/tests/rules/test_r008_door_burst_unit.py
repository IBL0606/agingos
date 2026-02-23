from __future__ import annotations

from datetime import datetime, timezone, timedelta

from services.rules.context import RuleContext
from services.rules.r008 import eval_r008_door_burst


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
    return RuleContext(session=_DB(rows), since=since, until=until, now=now, params=params or {})


def test_r008_no_trigger_below_threshold():
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    base = now - timedelta(minutes=20)
    rows = []
    # 5 door events in inngang (threshold default is 6)
    for i in range(5):
        rows.append(_Event(base + timedelta(minutes=i), f"d{i}", "door", {"room_id": "inngang"}))

    devs = eval_r008_door_burst(_ctx(rows, now, params={"tz": "UTC", "lookback_minutes": 30, "burst_threshold": 6}))
    assert devs == []


def test_r008_triggers_medium_on_burst_daytime():
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)  # daytime UTC
    base = now - timedelta(minutes=20)
    rows = []
    for i in range(6):
        rows.append(_Event(base + timedelta(minutes=i), f"d{i}", "door", {"room_id": "inngang"}))

    devs = eval_r008_door_burst(_ctx(rows, now, params={"tz": "UTC", "lookback_minutes": 30, "burst_threshold": 6}))
    assert len(devs) == 1
    assert devs[0].rule_id == "R-008"
    assert devs[0].severity == "MEDIUM"
    assert devs[0].evidence["door_event_count"] == 6


def test_r008_night_boost_to_high():
    now = datetime(2026, 2, 22, 23, 30, tzinfo=timezone.utc)  # night in UTC with 22->7 window
    base = now - timedelta(minutes=20)
    rows = []
    for i in range(6):
        rows.append(_Event(base + timedelta(minutes=i), f"d{i}", "door", {"room_id": "inngang"}))

    devs = eval_r008_door_burst(
        _ctx(
            rows,
            now,
            params={
                "tz": "UTC",
                "night_start_hour": 22,
                "night_end_hour": 7,
                "lookback_minutes": 30,
                "burst_threshold": 6,
            },
        )
    )
    assert len(devs) == 1
    assert devs[0].severity == "HIGH"
    assert devs[0].evidence["night"] is True


def test_r008_quiet_after_boost_bumps_severity():
    # Daytime, but quiet-after should bump MEDIUM->HIGH
    now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    base = now - timedelta(minutes=20)
    rows = []
    # door burst
    for i in range(6):
        rows.append(_Event(base + timedelta(minutes=i), f"d{i}", "door", {"room_id": "inngang"}))
    # No presence/motion rows at all after last door -> quiet_after=True

    devs = eval_r008_door_burst(
        _ctx(
            rows,
            now,
            params={
                "tz": "UTC",
                "lookback_minutes": 30,
                "burst_threshold": 6,
                "quiet_after_minutes": 10,
                "quiet_categories": ["presence", "motion"],
            },
        )
    )
    assert len(devs) == 1
    assert devs[0].severity == "HIGH"
    assert devs[0].evidence["quiet_after"] is True
