import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text

from app.database import engine, init_db

MIGRATIONS = [
    "DROP TABLE IF EXISTS job_embeddings",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS search_category_id VARCHAR",
    "ALTER TABLE user_job_matches ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'pending'",
    "ALTER TABLE user_job_matches ADD COLUMN IF NOT EXISTS applied_at TIMESTAMPTZ",
    "ALTER TABLE user_job_matches ADD COLUMN IF NOT EXISTS resume_years_experience DOUBLE PRECISION",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS temp_password_hash VARCHAR",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS temp_password_expires_at TIMESTAMPTZ",
]


def main():
    init_db()  # Create any missing tables first
    with engine.connect() as conn:
        for sql in MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
                print("OK:", sql)
            except Exception as e:
                print("Skip:", e)
                conn.rollback()
    print("Migration done.")


if __name__ == "__main__":
    main()
