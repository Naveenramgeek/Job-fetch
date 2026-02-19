from datetime import datetime, timezone

import app.services.pipeline_scheduler as sched


class _DB:
    def __init__(self):
        self.closed = False

    def execute(self, *_args, **_kwargs):
        class _Row:
            def first(self):
                return [True]

        return _Row()

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        self.closed = True


class _Result:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


def test_run_pipeline_once_calls_components(monkeypatch):
    db = _DB()
    monkeypatch.setattr(sched, "init_db", lambda: None)
    monkeypatch.setattr(sched, "SessionLocal", lambda: db)
    monkeypatch.setattr(sched, "seed_default_categories", lambda db: ([], 0))
    monkeypatch.setattr(sched, "run_collector", lambda db: {"fetched": 1})
    monkeypatch.setattr(sched, "run_deep_match_all", lambda db: {"scored": 2})
    out = sched._run_pipeline_once()
    assert out["collector"]["fetched"] == 1
    assert out["deep_match"]["scored"] == 2
    assert db.closed is True


def test_start_stop_status_and_double_start(monkeypatch):
    state = {"enabled": False, "last_run": datetime.now(timezone.utc), "next_run": datetime.now(timezone.utc)}
    monkeypatch.setattr(sched, "_read_state", lambda: (state["enabled"], state["last_run"], state["next_run"]))
    monkeypatch.setattr(sched, "_set_enabled", lambda enabled: state.__setitem__("enabled", enabled))
    monkeypatch.setattr(sched, "_set_next_run", lambda next_run: state.__setitem__("next_run", next_run))
    monkeypatch.setattr(sched, "_ensure_thread_running", lambda: None)

    ok1, msg1 = sched.start_scheduler()
    ok2, msg2 = sched.start_scheduler()
    ok3, msg3 = sched.stop_scheduler()
    status = sched.get_status()

    assert ok1 is True and "Pipeline started" in msg1
    assert ok2 is False and "already" in msg2
    assert ok3 is True and "stop requested" in msg3
    assert status["running"] is False


def test_start_scheduler_seconds_human_message(monkeypatch):
    state = {"enabled": False, "last_run": None, "next_run": None}
    monkeypatch.setattr(sched, "_read_state", lambda: (state["enabled"], state["last_run"], state["next_run"]))
    monkeypatch.setattr(sched, "_set_enabled", lambda enabled: state.__setitem__("enabled", enabled))
    monkeypatch.setattr(sched, "_set_next_run", lambda next_run: state.__setitem__("next_run", next_run))
    monkeypatch.setattr(sched, "_ensure_thread_running", lambda: None)
    sched.INTERVAL_SECONDS = 30
    ok, msg = sched.start_scheduler()
    assert ok is True
    assert "seconds" in msg
    sched.stop_scheduler()


def test_stop_scheduler_when_not_running(monkeypatch):
    monkeypatch.setattr(sched, "_read_state", lambda: (False, None, None))
    ok, msg = sched.stop_scheduler()
    assert ok is False
    assert "not running" in msg


def test_scheduler_loop_runs_once_and_stops(monkeypatch):
    calls = {"n": 0, "enabled": True, "next_run": datetime.now(timezone.utc)}

    def fake_run_once():
        calls["n"] += 1
        return {}

    def fake_sleep(_seconds):
        calls["enabled"] = False

    monkeypatch.setattr(sched, "_read_state", lambda: (calls["enabled"], None, calls["next_run"]))
    monkeypatch.setattr(sched, "_set_run_times", lambda last_run, next_run: calls.update(next_run=next_run))
    monkeypatch.setattr(sched, "_set_next_run", lambda next_run: calls.update(next_run=next_run))
    sched.INTERVAL_SECONDS = 1
    monkeypatch.setattr(sched, "_run_pipeline_once", fake_run_once)
    monkeypatch.setattr(sched.time, "sleep", fake_sleep)
    sched._running = True
    sched._thread = object()
    sched._scheduler_loop()
    assert calls["n"] == 1


def test_scheduler_loop_waits_for_next_run_after_restart(monkeypatch):
    calls = {"n": 0, "enabled": True, "next_run": datetime.now(timezone.utc) + sched.timedelta(seconds=120)}

    def fake_run_once():
        calls["n"] += 1
        return {}

    def fake_sleep(_seconds):
        calls["enabled"] = False

    monkeypatch.setattr(sched, "_read_state", lambda: (calls["enabled"], None, calls["next_run"]))
    monkeypatch.setattr(sched, "_run_pipeline_once", fake_run_once)
    monkeypatch.setattr(sched.time, "sleep", fake_sleep)
    sched._running = True
    sched._thread = object()
    sched._scheduler_loop()
    assert calls["n"] == 0


def test_recover_scheduler_from_db_starts_thread_when_enabled(monkeypatch):
    monkeypatch.setattr(sched, "_read_state", lambda: (True, None, None))
    called = {"started": False}
    monkeypatch.setattr(sched, "_ensure_thread_running", lambda: called.__setitem__("started", True))
    sched.recover_scheduler_from_db()
    assert called["started"] is True


def test_recover_scheduler_from_db_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(sched, "_read_state", lambda: (False, None, None))
    called = {"started": False}
    monkeypatch.setattr(sched, "_ensure_thread_running", lambda: called.__setitem__("started", True))
    sched.recover_scheduler_from_db()
    assert called["started"] is False


def test_read_state_returns_defaults_when_no_row(monkeypatch):
    class _ReadDB(_DB):
        def execute(self, *_args, **_kwargs):
            return _Result(None)

    monkeypatch.setattr(sched, "SessionLocal", lambda: _ReadDB())
    monkeypatch.setattr(sched, "_ensure_state_row", lambda db: None)
    enabled, last_run, next_run = sched._read_state()
    assert enabled is False
    assert last_run is None
    assert next_run is None


def test_read_state_returns_values(monkeypatch):
    now = datetime.now(timezone.utc)

    class _ReadDB(_DB):
        def execute(self, *_args, **_kwargs):
            return _Result((True, now, now))

    monkeypatch.setattr(sched, "SessionLocal", lambda: _ReadDB())
    monkeypatch.setattr(sched, "_ensure_state_row", lambda db: None)
    enabled, last_run, next_run = sched._read_state()
    assert enabled is True
    assert last_run == now
    assert next_run == now


def test_setters_execute_without_error(monkeypatch):
    db = _DB()
    monkeypatch.setattr(sched, "SessionLocal", lambda: db)
    monkeypatch.setattr(sched, "_ensure_state_row", lambda _db: None)
    now = datetime.now(timezone.utc)
    sched._set_enabled(True)
    sched._set_run_times(now, now)
    sched._set_next_run(now)
    assert db.closed is True


def test_is_enabled_reads_state(monkeypatch):
    monkeypatch.setattr(sched, "_read_state", lambda: (True, None, None))
    assert sched._is_enabled() is True


def test_try_acquire_distributed_lock_handles_exception(monkeypatch):
    class _BadDB:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("no advisory lock support")

    assert sched._try_acquire_distributed_lock(_BadDB()) is True


def test_release_distributed_lock_handles_exception():
    class _BadDB:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("boom")

        def commit(self):
            return None

        def rollback(self):
            self.rolled_back = True

    db = _BadDB()
    sched._release_distributed_lock(db)
    assert getattr(db, "rolled_back", False) is True


def test_scheduler_loop_sets_next_run_on_failure(monkeypatch):
    calls = {"enabled": True, "set_next": False}

    monkeypatch.setattr(sched, "_read_state", lambda: (calls["enabled"], None, datetime.now(timezone.utc)))

    def _boom():
        raise RuntimeError("collector failed")

    def _fake_sleep(_seconds):
        calls["enabled"] = False

    monkeypatch.setattr(sched, "_run_pipeline_once", _boom)
    monkeypatch.setattr(
        sched,
        "_set_next_run",
        lambda _dt: (calls.__setitem__("set_next", True), calls.__setitem__("enabled", False)),
    )
    monkeypatch.setattr(sched.time, "sleep", _fake_sleep)
    sched._running = True
    sched._thread = object()
    sched._scheduler_loop()
    assert calls["set_next"] is True
