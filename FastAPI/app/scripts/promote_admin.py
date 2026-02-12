"""
Promote a user to admin by email.
Usage: python -m app.scripts.promote_admin user@example.com
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database import SessionLocal, ensure_tables_exist
from app.repos.user_repo import get_by_email, update


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m app.scripts.promote_admin <email>")
        sys.exit(1)
    email = sys.argv[1].strip()
    ensure_tables_exist()
    db = SessionLocal()
    try:
        user = get_by_email(db, email)
        if not user:
            print(f"User not found: {email}")
            sys.exit(1)
        update(db, user.id, is_admin=True)
        print(f"Promoted {email} to admin.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
