"""
Background scheduler that runs the job pipeline (collector + deep match)
every configured interval (`PIPELINE_INTERVAL_SECONDS`).
Start/stop via API; state is in-process only (resets on server restart).
"""
import logging
import threading
import time
from datetime import datetime, timezone, timedelta

from app.config import settings
from app.database import SessionLocal, init_db
from app.repos.search_category_repo import seed_default_categories
from app.repos.job_listing_repo import delete_unmatched as delete_unmatched_job_listings
from app.services.job_collector import run_collector
from app.services.deep_match_service import run_deep_match_all

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = settings.pipeline_interval_seconds

_lock = threading.Lock()
_running = False
_thread: threading.Thread | None = None
_last_run: datetime | None = None
_next_run: datetime | None = None


def _run_pipeline_once() -> dict:
    """Run collector + deep match once. Uses its own DB session. Call from scheduler thread."""
    init_db()
    db = SessionLocal()
    try:
        seed_default_categories(db)
        collector_result = run_collector(db)
        deep_result = run_deep_match_all(db)
        cleanup_count = delete_unmatched_job_listings(db)
        logger.info(
            "Scheduled pipeline run: collector=%s deep_match=%s cleanup_unmatched=%d",
            collector_result, deep_result, cleanup_count,
        )
        return {
            "collector": collector_result,
            "deep_match": deep_result,
            "cleanup_unmatched": cleanup_count,
        }
    finally:
        db.close()


def _scheduler_loop() -> None:
    global _last_run, _next_run
    logger.info("Pipeline scheduler thread started")
    while True:
        with _lock:
            if not _running:
                break
        try:
            _run_pipeline_once()
        except Exception as e:
            logger.exception("Scheduled pipeline run failed: %s", e)
        with _lock:
            _last_run = datetime.now(timezone.utc)
            if not _running:
                _next_run = None
                break
            _next_run = datetime.now(timezone.utc) + timedelta(seconds=INTERVAL_SECONDS)
        time.sleep(INTERVAL_SECONDS)
    logger.info("Pipeline scheduler thread stopped")


def start_scheduler() -> tuple[bool, str]:
    """
    Start the recurring pipeline (run now, then every configured interval).
    Returns (success, message).
    """
    global _running, _thread
    with _lock:
        if _running:
            return False, "Pipeline is already running"
        _running = True
        _thread = threading.Thread(target=_scheduler_loop, daemon=True)
        _thread.start()
    if INTERVAL_SECONDS % 3600 == 0:
        human = f"{INTERVAL_SECONDS // 3600} hours"
    else:
        human = f"{INTERVAL_SECONDS} seconds"
    return True, f"Pipeline started (runs every {human})"


def stop_scheduler() -> tuple[bool, str]:
    """Stop the recurring pipeline. Current run finishes; next run is skipped."""
    global _running, _next_run
    with _lock:
        if not _running:
            return False, "Pipeline is not running"
        _running = False
        _next_run = None
    return True, "Pipeline stop requested (will stop after current run)"


def get_status() -> dict:
    """Return current scheduler status."""
    with _lock:
        return {
            "running": _running,
            "last_run": _last_run.isoformat() if _last_run else None,
            "next_run": _next_run.isoformat() if _next_run else None,
            "interval_hours": INTERVAL_SECONDS / 3600,
        }
