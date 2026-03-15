from __future__ import annotations

from routes.rules import _resolve_scope


class _Result:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _DBOk:
    def execute(self, *_args, **_kwargs):
        return _Result({"org_id": "o1", "home_id": "h1", "subject_id": "s1"})


class _DBMissingTable:
    def execute(self, *_args, **_kwargs):
        raise RuntimeError('psycopg2.errors.UndefinedTable: relation "subjects" does not exist')


def test_resolve_scope_returns_row_values_when_available():
    assert _resolve_scope(_DBOk()) == ("o1", "h1", "s1")


def test_resolve_scope_falls_back_to_default_when_subjects_missing():
    assert _resolve_scope(_DBMissingTable()) == ("default", "default", "default")
