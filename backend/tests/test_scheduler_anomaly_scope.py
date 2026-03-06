from sqlalchemy.exc import ProgrammingError

from services.scheduler import _anomaly_pick_one_scope, run_anomalies_job


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _FakeDB:
    def __init__(self, row=None, exc=None):
        self.row = row
        self.exc = exc
        self.rollback_calls = 0
        self.commit_calls = 0
        self.close_calls = 0

    def execute(self, *args, **kwargs):
        if self.exc:
            raise self.exc
        return _FakeResult(self.row)

    def rollback(self):
        self.rollback_calls += 1

    def commit(self):
        self.commit_calls += 1

    def close(self):
        self.close_calls += 1


def test_anomaly_pick_one_scope_fallback_rolls_back_on_programming_error():
    db = _FakeDB(exc=ProgrammingError("select", {}, Exception("missing column")))

    scope = _anomaly_pick_one_scope(db)

    assert db.rollback_calls == 1
    assert scope.org_id == "default"
    assert scope.home_id == "default"
    assert scope.subject_id == "default"
    assert scope.user_id == "system"


def test_anomaly_pick_one_scope_ignores_missing_user_id_column():
    db = _FakeDB(row={"org_id": "o1", "home_id": "h1", "subject_id": "s1"})

    scope = _anomaly_pick_one_scope(db)

    assert scope.org_id == "o1"
    assert scope.home_id == "h1"
    assert scope.subject_id == "s1"
    assert scope.user_id == "system"


def test_run_anomalies_job_rolls_back_and_continues_per_room(monkeypatch):
    db = _FakeDB()

    monkeypatch.setattr("db.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "services.scheduler._anomaly_pick_one_scope",
        lambda _db: type("S", (), {"org_id": "o", "home_id": "h", "subject_id": "s"})(),
    )
    monkeypatch.setattr("services.scheduler._anomaly_list_room_ids", lambda _db, scope: ["r1", "r2"])

    calls = {"n": 0}

    def _run_one(_db, *, scope, room, bucket_start):
        calls["n"] += 1
        if room == "r1":
            raise RuntimeError("boom")
        return {"action": "OPEN"}

    monkeypatch.setattr("services.scheduler.run_anomalies_job_one", _run_one)

    out = run_anomalies_job()

    assert calls["n"] == 2
    assert db.rollback_calls == 1
    assert db.commit_calls == 1
    assert out["counts"]["ERROR"] == 1
    assert out["counts"]["OPEN"] == 1
