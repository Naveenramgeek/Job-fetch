import os

import pytest

import app.scripts.clear_jobs as clear_jobs
import app.scripts.migrate_db as migrate
import app.scripts.promote_admin as promote
import app.scripts.run_collector_pipeline as rcp
import app.scripts.init_db_production as initdb


def test_migrate_main_runs_all_sql(monkeypatch):
    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, _sql):
            return None

        def commit(self):
            return None

        def rollback(self):
            return None

    monkeypatch.setattr(migrate, "init_db", lambda: None)
    monkeypatch.setattr(migrate.engine, "connect", lambda: _Conn())
    migrate.main()


def test_promote_admin_user_not_found(monkeypatch):
    monkeypatch.setattr(promote, "init_db", lambda: None)
    monkeypatch.setattr(promote, "SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr(promote, "get_by_email", lambda db, email: None)
    monkeypatch.setattr(promote.sys, "argv", ["prog", "missing@example.com"])
    with pytest.raises(SystemExit):
        promote.main()


def test_run_collector_pipeline_run_pipeline(monkeypatch):
    monkeypatch.setattr(rcp, "init_db", lambda: None)
    monkeypatch.setattr(rcp, "seed_default_categories", lambda db: ([], 0))
    monkeypatch.setattr(rcp, "run_collector", lambda db: {"fetched": 1})
    monkeypatch.setattr(rcp, "run_deep_match_all", lambda db: {"scored": 2})
    monkeypatch.setattr(rcp, "delete_unmatched_job_listings", lambda db: 3)
    out = rcp.run_pipeline(db=object())
    assert out["collector"]["fetched"] == 1
    assert out["deep_match"]["scored"] == 2
    assert out["cleanup_unmatched"] == 3


def test_init_db_production_helpers(monkeypatch):
    parsed = initdb.parse_db_url("postgresql://user:pass@localhost:5432/resume_db")
    assert parsed["user"] == "user"
    assert parsed["dbname"] == "resume_db"

    monkeypatch.setenv("POSTGRES_ADMIN_USER", "postgres")
    monkeypatch.setenv("POSTGRES_ADMIN_PASSWORD", "secret")
    admin_url = initdb.build_admin_url("postgresql://user:pass@localhost:5432/resume_db")
    assert admin_url.endswith("/postgres")


def test_init_db_production_main_rejects_invalid_identifier(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://bad-user:pass@localhost:5432/resume_db")
    rc = initdb.main()
    assert rc == 1
    os.environ.pop("DATABASE_URL", None)


def test_clear_jobs_aborts_without_confirmation(monkeypatch):
    monkeypatch.setattr(clear_jobs.sys, "argv", ["prog"])
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    with pytest.raises(SystemExit):
        clear_jobs.main()


def test_clear_jobs_yes_executes_deletes(monkeypatch):
    monkeypatch.setattr(clear_jobs.sys, "argv", ["prog", "--yes"])

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, _sql):
            return type("R", (), {"rowcount": 2})()

    monkeypatch.setattr(clear_jobs.engine, "begin", lambda: _Conn())
    clear_jobs.main()


def test_promote_admin_success(monkeypatch):
    user = type("U", (), {"id": "u1"})()
    db = type("DB", (), {"close": lambda self: None})()
    monkeypatch.setattr(promote, "init_db", lambda: None)
    monkeypatch.setattr(promote, "SessionLocal", lambda: db)
    monkeypatch.setattr(promote, "get_by_email", lambda db, email: user)
    monkeypatch.setattr(promote, "update", lambda db, uid, **kwargs: user)
    monkeypatch.setattr(promote.sys, "argv", ["prog", "a@b.com"])
    promote.main()


def test_run_collector_pipeline_main_once_collect_only(monkeypatch):
    db = type("DB", (), {"close": lambda self: None})()
    monkeypatch.setattr(rcp, "init_db", lambda: None)
    monkeypatch.setattr(rcp, "SessionLocal", lambda: db)
    monkeypatch.setattr(rcp, "seed_default_categories", lambda db: ([], 0))
    monkeypatch.setattr(rcp, "run_collector", lambda db: {"fetched": 1})
    monkeypatch.setattr(rcp, "run_deep_match_all", lambda db: {"scored": 2})
    monkeypatch.setattr(rcp, "delete_unmatched_job_listings", lambda db: 3)
    monkeypatch.setattr(rcp, "INTERVAL_SECONDS", 1)
    monkeypatch.setattr(rcp.argparse.ArgumentParser, "parse_args", lambda self: type("A", (), {"once": True, "collect_only": True})())
    rcp.main()


def test_run_collector_pipeline_main_loop_handles_failure(monkeypatch):
    db = type("DB", (), {"close": lambda self: None})()
    monkeypatch.setattr(rcp, "init_db", lambda: None)
    monkeypatch.setattr(rcp, "SessionLocal", lambda: db)
    monkeypatch.setattr(rcp, "seed_default_categories", lambda db: ([], 0))
    monkeypatch.setattr(rcp, "run_pipeline", lambda db: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(rcp.argparse.ArgumentParser, "parse_args", lambda self: type("A", (), {"once": False, "collect_only": False})())
    monkeypatch.setattr(rcp.time, "sleep", lambda s: (_ for _ in ()).throw(SystemExit(0)))
    with pytest.raises(SystemExit):
        rcp.main()


def test_init_db_production_main_success(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://resume_user:pwd@localhost:5432/resume_db")
    monkeypatch.delenv("POSTGRES_ADMIN_URL", raising=False)
    monkeypatch.setenv("POSTGRES_ADMIN_USER", "postgres")
    monkeypatch.setenv("POSTGRES_ADMIN_PASSWORD", "adminpwd")

    class _Conn:
        def set_isolation_level(self, _lvl):
            return None

        def close(self):
            return None

        def cursor(self):
            class _Cur:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def execute(self, sql, params=()):
                    self.sql = sql
                    self.params = params

                def fetchone(self):
                    return None

            return _Cur()

    monkeypatch.setattr(initdb.psycopg2, "connect", lambda *args, **kwargs: _Conn())
    rc = initdb.main()
    assert rc == 0
