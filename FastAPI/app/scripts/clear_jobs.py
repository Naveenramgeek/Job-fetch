"""
Delete all job-related data from the database in a single transaction.
Order: user_job_matches -> job_listings -> jobs (respects foreign keys).

Requires project dependencies (e.g. SQLAlchemy). From repo root:
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r FastAPI/requirements.txt
  python -m FastAPI.app.scripts.clear_jobs [--yes]
"""
import argparse
import sys
from pathlib import Path

# Project root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text

from app.database import engine


# Tables to clear, in FK-safe order (dependents first)
TABLES = ["user_job_matches", "job_listings", "jobs"]


def main():
    parser = argparse.ArgumentParser(description="Delete all users' jobs and job-related data from the database.")
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    if not args.yes:
        print("This will permanently delete all data from:")
        for t in TABLES:
            print(f"  - {t}")
        print("Users and search_categories will NOT be deleted.")
        try:
            reply = input("Type 'yes' to continue: ").strip().lower()
        except EOFError:
            reply = ""
        if reply != "yes":
            print("Aborted.")
            sys.exit(1)

    deleted = {}
    with engine.begin() as conn:
        # Single transaction: all deletes, then one commit at end of block
        for table in TABLES:
            result = conn.execute(text(f"DELETE FROM {table}"))
            deleted[table] = result.rowcount
            print(f"Deleted {deleted[table]} row(s) from {table}")

    total = sum(deleted.values())
    print(f"Done. Total rows removed: {total}")


if __name__ == "__main__":
    main()
