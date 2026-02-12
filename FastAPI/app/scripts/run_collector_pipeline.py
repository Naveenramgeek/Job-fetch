import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure app is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, init_db
from app.repos.search_category_repo import seed_default_categories
from app.repos.job_listing_repo import delete_unmatched as delete_unmatched_job_listings
from app.services.job_collector import run_collector
from app.services.deep_match_service import run_deep_match_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
INTERVAL_SECONDS = settings.pipeline_interval_seconds


def run_pipeline(db: Session) -> dict:
    """Run collector + deep match. Returns combined stats."""
    init_db()
    seed_default_categories(db)

    collector_result = run_collector(db)
    deep_result = run_deep_match_all(db)
    cleanup_count = delete_unmatched_job_listings(db)

    return {
        "collector": collector_result,
        "deep_match": deep_result,
        "cleanup_unmatched": cleanup_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Job collector pipeline (every 2h or once)")
    parser.add_argument("--once", action="store_true", help="Run once and exit (no schedule)")
    parser.add_argument("--collect-only", action="store_true", help="Only run collector, skip deep match")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        seed_default_categories(db)
    finally:
        db.close()

    if args.once:
        db = SessionLocal()
        try:
            result = run_collector(db)
            logger.info("Collector result: %s", result)
            if not args.collect_only:
                deep_result = run_deep_match_all(db)
                logger.info("Deep match result: %s", deep_result)
                cleanup_count = delete_unmatched_job_listings(db)
                logger.info("Cleanup unmatched: %d", cleanup_count)
        finally:
            db.close()
        return

    # Scheduled loop
    while True:
        db = SessionLocal()
        try:
            result = run_pipeline(db)
            logger.info("Pipeline result: %s", result)
        except Exception as e:
            logger.exception("Pipeline failed: %s", e)
        finally:
            db.close()
        logger.info("Sleeping %d seconds until next run", INTERVAL_SECONDS)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
