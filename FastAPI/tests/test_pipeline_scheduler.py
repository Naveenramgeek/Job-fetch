from datetime import datetime, timezone

import app.services.pipeline_scheduler as sched


class _DB:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_run_pipeline_once_calls_components(monkeypatch):
    db = _DB()
    monkeypatch.setattr(sched, "init_db", lambda: None)
    monkeypatch.setattr(sched, "SessionLocal", lambda: db)
    monkeypatch.setattr(sched, "seed_default_categories", lambda db: ([], 0))
    monkeypatch.setattr(sched, "run_collector", lambda db: {"fetched": 1})
    monkeypatch.setattr(sched, "run_deep_match_all", lambda db: {"scored": 2})
    monkeypatch.setattr(sched, "delete_unmatched_job_listings", lambda db: 3)

    out = sched._run_pipeline_once()
    assert out["collector"]["fetched"] == 1
    assert out["deep_match"]["scored"] == 2
    assert out["cleanup_unmatched"] == 3
    assert db.closed is True


def test_start_stop_status_and_double_start(monkeypatch):
    monkeypatch.setattr(sched, "_scheduler_loop", lambda: None)
    sched._running = False
    sched._thread = None
    sched._last_run = datetime.now(timezone.utc)
    sched._next_run = datetime.now(timezone.utc)

    ok1, msg1 = sched.start_scheduler()
    ok2, msg2 = sched.start_scheduler()
    ok3, msg3 = sched.stop_scheduler()
    status = sched.get_status()

    assert ok1 is True and "Pipeline started" in msg1
    assert ok2 is False and "already" in msg2
    assert ok3 is True and "stop requested" in msg3
    assert status["running"] is False


def test_start_scheduler_seconds_human_message(monkeypatch):
    monkeypatch.setattr(sched, "_scheduler_loop", lambda: None)
    sched._running = False
    sched.INTERVAL_SECONDS = 30
    ok, msg = sched.start_scheduler()
    assert ok is True
    assert "seconds" in msg
    sched.stop_scheduler()


def test_stop_scheduler_when_not_running():
    sched._running = False
    ok, msg = sched.stop_scheduler()
    assert ok is False
    assert "not running" in msg


def test_scheduler_loop_runs_once_and_stops(monkeypatch):
    calls = {"n": 0}

    def fake_run_once():
        calls["n"] += 1
        return {}

    def fake_sleep(_seconds):
        sched._running = False

    sched._running = True
    monkeypatch.setattr(sched, "_run_pipeline_once", fake_run_once)
    monkeypatch.setattr(sched.time, "sleep", fake_sleep)
    sched._scheduler_loop()
    assert calls["n"] == 1
