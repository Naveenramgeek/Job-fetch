"""
Background scheduler that runs the job pipeline (collector + deep match)
every configured interval (`PIPELINE_INTERVAL_SECONDS`).
Start/stop via API; state is persisted in DB so it survives process restarts.
"""
import logging
import threading
import time
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal, init_db
from app.repos.search_category_repo import seed_default_categories
from app.services.job_collector import run_collector
from app.services.deep_match_service import run_deep_match_all

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = settings.pipeline_interval_seconds
STATE_ID = "default"
PG_ADVISORY_LOCK_KEY = 89021041

_lock = threading.Lock()
_running = False
_thread: threading.Thread | None = None


def _ensure_state_row(db) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS pipeline_scheduler_state (
                id VARCHAR PRIMARY KEY,
                enabled BOOLEAN NOT NULL DEFAULT FALSE,
                last_run_at TIMESTAMPTZ NULL,
                next_run_at TIMESTAMPTZ NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    db.execute(
        text(
            """
            INSERT INTO pipeline_scheduler_state (id, enabled)
            VALUES (:id, FALSE)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": STATE_ID},
    )
    db.commit()


def _read_state() -> tuple[bool, datetime | None, datetime | None]:
    db = SessionLocal()
    try:
        _ensure_state_row(db)
        row = db.execute(
            text(
                """
                SELECT enabled, last_run_at, next_run_at
                FROM pipeline_scheduler_state
                WHERE id = :id
                """
            ),
            {"id": STATE_ID},
        ).first()
        if not row:
            return False, None, None
        return bool(row[0]), row[1], row[2]
    finally:
        db.close()


def _set_enabled(enabled: bool) -> None:
    db = SessionLocal()
    try:
        _ensure_state_row(db)
        db.execute(
            text(
                """
                UPDATE pipeline_scheduler_state
                SET enabled = :enabled,
                    next_run_at = CASE WHEN :enabled THEN next_run_at ELSE NULL END,
                    updated_at = NOW()
                WHERE id = :id
                """
            ),
            {"id": STATE_ID, "enabled": enabled},
        )
        db.commit()
    finally:
        db.close()


def _set_run_times(last_run: datetime | None, next_run: datetime | None) -> None:
    db = SessionLocal()
    try:
        _ensure_state_row(db)
        db.execute(
            text(
                """
                UPDATE pipeline_scheduler_state
                SET last_run_at = :last_run,
                    next_run_at = :next_run,
                    updated_at = NOW()
                WHERE id = :id
                """
            ),
            {"id": STATE_ID, "last_run": last_run, "next_run": next_run},
        )
        db.commit()
    finally:
        db.close()


def _set_next_run(next_run: datetime | None) -> None:
    db = SessionLocal()
    try:
        _ensure_state_row(db)
        db.execute(
            text(
                """
                UPDATE pipeline_scheduler_state
                SET next_run_at = :next_run,
                    updated_at = NOW()
                WHERE id = :id
                """
            ),
            {"id": STATE_ID, "next_run": next_run},
        )
        db.commit()
    finally:
        db.close()


def _is_enabled() -> bool:
    enabled, _, _ = _read_state()
    return enabled


def _try_acquire_distributed_lock(db) -> bool:
    try:
        row = db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": PG_ADVISORY_LOCK_KEY}).first()
        return bool(row and row[0])
    except Exception:
        # Non-Postgres environments do not support advisory locks.
        return True


def _release_distributed_lock(db) -> None:
    try:
        db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": PG_ADVISORY_LOCK_KEY})
        db.commit()
    except Exception:
        db.rollback()


def _run_pipeline_once() -> dict:
    """Run collector + deep match once. Uses its own DB session. Call from scheduler thread."""
    init_db()
    db = SessionLocal()
    locked = False
    try:
        locked = _try_acquire_distributed_lock(db)
        if not locked:
            logger.info("Skipping scheduler run in this process (lock held elsewhere)")
            return {"skipped": True}
        seed_default_categories(db)
        collector_result = run_collector(db)
        deep_result = run_deep_match_all(db)
        logger.info(
            "Scheduled pipeline run: collector=%s deep_match=%s",
            collector_result, deep_result,
        )
        return {
            "collector": collector_result,
            "deep_match": deep_result,
            "skipped": False,
        }
    finally:
        if locked:
            _release_distributed_lock(db)
        db.close()


def _scheduler_loop() -> None:
    global _running, _thread
    logger.info("Pipeline scheduler thread started")
    while True:
        enabled, _, next_run = _read_state()
        if not enabled:
            break
        now = datetime.now(timezone.utc)
        if next_run and next_run > now:
            sleep_seconds = (next_run - now).total_seconds()
            time.sleep(min(5, max(0.5, sleep_seconds)))
            continue
        try:
            out = _run_pipeline_once()
            run_time = datetime.now(timezone.utc)
            if out.get("skipped"):
                # Another process is performing this due run; avoid tight polling.
                time.sleep(5)
                continue
            _set_run_times(last_run=run_time, next_run=run_time + timedelta(seconds=INTERVAL_SECONDS))
        except Exception as e:
            logger.exception("Scheduled pipeline run failed: %s", e)
            # Keep cadence on failure by scheduling the next attempt after interval.
            _set_next_run(datetime.now(timezone.utc) + timedelta(seconds=INTERVAL_SECONDS))
    with _lock:
        _running = False
        _thread = None
    logger.info("Pipeline scheduler thread stopped")


def _ensure_thread_running() -> None:
    global _running, _thread
    with _lock:
        if _thread and _thread.is_alive():
            _running = True
            return
        _running = True
        _thread = threading.Thread(target=_scheduler_loop, daemon=True)
        _thread.start()


def recover_scheduler_from_db() -> None:
    """Start scheduler thread on process startup if DB state says it is enabled."""
    enabled, _, _ = _read_state()
    if enabled:
        _ensure_thread_running()


def start_scheduler() -> tuple[bool, str]:
    """
    Start the recurring pipeline (run now, then every configured interval).
    Returns (success, message).
    """
    enabled, _, _ = _read_state()
    if enabled:
        _ensure_thread_running()
        return False, "Pipeline is already running"
    _set_enabled(True)
    _set_next_run(datetime.now(timezone.utc))
    _ensure_thread_running()
    if INTERVAL_SECONDS % 3600 == 0:
        human = f"{INTERVAL_SECONDS // 3600} hours"
    else:
        human = f"{INTERVAL_SECONDS} seconds"
    return True, f"Pipeline started (runs every {human})"


def stop_scheduler() -> tuple[bool, str]:
    """Stop the recurring pipeline. Current run finishes; next run is skipped."""
    enabled, _, _ = _read_state()
    if not enabled:
        return False, "Pipeline is not running"
    _set_enabled(False)
    return True, "Pipeline stop requested (will stop after current run)"


def get_status() -> dict:
    """Return current scheduler status."""
    enabled, last_run, next_run = _read_state()
    return {
        "running": enabled,
        "last_run": last_run.isoformat() if last_run else None,
        "next_run": next_run.isoformat() if next_run and enabled else None,
        "interval_hours": INTERVAL_SECONDS / 3600,
    }
