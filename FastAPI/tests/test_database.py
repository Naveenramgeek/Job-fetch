import pytest

import app.database as dbmod


def test_get_db_closes_session(monkeypatch):
    class _DB:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    inst = _DB()
    monkeypatch.setattr(dbmod, "SessionLocal", lambda: inst)
    gen = dbmod.get_db()
    got = next(gen)
    assert got is inst
    with pytest.raises(StopIteration):
        next(gen)
    assert inst.closed is True


def test_init_db_success_and_failure(monkeypatch):
    class _Meta:
        def create_all(self, bind):
            return None

    monkeypatch.setattr(dbmod.Base, "metadata", _Meta())
    dbmod.init_db()

    class _MetaFail:
        def create_all(self, bind):
            raise RuntimeError("db fail")

    monkeypatch.setattr(dbmod.Base, "metadata", _MetaFail())
    with pytest.raises(RuntimeError):
        dbmod.init_db()


def test_ensure_tables_exist_creates_only_missing(monkeypatch):
    class _Inspector:
        def get_table_names(self):
            return ["users"]

    class _Meta:
        tables = {"users": object(), "jobs": object()}

        def create_all(self, bind):
            return None

    monkeypatch.setattr(dbmod, "inspect", lambda _engine: _Inspector())
    monkeypatch.setattr(dbmod.Base, "metadata", _Meta())
    dbmod.ensure_tables_exist()


def test_ensure_tables_exist_failure(monkeypatch):
    def _boom(_engine):
        raise RuntimeError("inspect failed")

    monkeypatch.setattr(dbmod, "inspect", _boom)
    with pytest.raises(RuntimeError):
        dbmod.ensure_tables_exist()
