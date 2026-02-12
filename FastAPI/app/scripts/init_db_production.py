#!/usr/bin/env python3
"""
Production database setup: creates role, database, and privileges.
Run once before deploying the app (or as part of CI/CD provisioning).

Requires a superuser connection (POSTGRES_ADMIN_URL) to create role/database.
The app's DATABASE_URL defines the target user, db, host, etc.

Usage:
  python -m app.scripts.init_db_production

Environment variables:
  DATABASE_URL             - App connection string (e.g. postgresql://resume_user:xxx@localhost:5432/resume_db)
  POSTGRES_ADMIN_URL       - Superuser connection for provisioning (optional; see below)
  POSTGRES_ADMIN_USER      - Fallback admin user when building admin URL (default: postgres)
  POSTGRES_ADMIN_PASSWORD  - Fallback admin password when building admin URL

If POSTGRES_ADMIN_URL is not set, the script builds it from DATABASE_URL by
replacing the database with "postgres" and using POSTGRES_ADMIN_USER/PASSWORD.
For managed DBs (RDS, Cloud SQL), create role/db via console first.
"""
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse, quote

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Use psycopg2 directly to avoid loading app
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Valid identifiers: alphanumeric + underscore (safe for SQL)
IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def parse_db_url(url: str) -> dict:
    """Parse postgresql:// URL into components."""
    parsed = urlparse(url)
    return {
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "dbname": (parsed.path or "/postgres").lstrip("/") or "postgres",
    }


def build_admin_url(database_url: str) -> str:
    """Build admin URL from DATABASE_URL using postgres db and admin credentials."""
    parsed = urlparse(database_url)
    admin_user = os.environ.get("POSTGRES_ADMIN_USER", "postgres")
    admin_pass = os.environ.get("POSTGRES_ADMIN_PASSWORD", parsed.password or "")
    # Rebuild netloc: user:pass@host:port (quote password for special chars)
    netloc = f"{quote(admin_user, safe='')}:{quote(admin_pass, safe='')}@{parsed.hostname or 'localhost'}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse((
        parsed.scheme or "postgresql",
        netloc,
        "/postgres",
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))


def run_sql(conn, sql: str, params=None) -> None:
    """Execute SQL."""
    with conn.cursor() as cur:
        cur.execute(sql, params or ())


def role_exists(conn, role: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
        return cur.fetchone() is not None


def database_exists(conn, dbname: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        return cur.fetchone() is not None


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    admin_url = os.environ.get("POSTGRES_ADMIN_URL")

    if not database_url:
        print("ERROR: DATABASE_URL is required.", file=sys.stderr)
        return 1

    db_params = parse_db_url(database_url)
    target_user = db_params["user"]
    target_db = db_params["dbname"]
    target_pass = db_params["password"]
    host = db_params["host"]
    port = db_params["port"]

    if not IDENT_RE.match(target_user):
        print(f"ERROR: Invalid role name '{target_user}' (alphanumeric + underscore only)", file=sys.stderr)
        return 1
    if not IDENT_RE.match(target_db):
        print(f"ERROR: Invalid database name '{target_db}' (alphanumeric + underscore only)", file=sys.stderr)
        return 1

    if not admin_url:
        admin_url = build_admin_url(database_url)
        print("POSTGRES_ADMIN_URL not set; using postgres db with POSTGRES_ADMIN_USER/PASSWORD")

    print(f"Provisioning database: {target_db}, user: {target_user} @ {host}:{port}")

    try:
        admin_conn = psycopg2.connect(admin_url)
        admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    except Exception as e:
        print(f"ERROR: Cannot connect as admin: {e}", file=sys.stderr)
        print("Set POSTGRES_ADMIN_URL (superuser) or POSTGRES_ADMIN_USER + POSTGRES_ADMIN_PASSWORD", file=sys.stderr)
        return 1

    try:
        # 1. Create role if not exists
        if not role_exists(admin_conn, target_user):
            run_sql(
                admin_conn,
                f'CREATE ROLE "{target_user}" WITH LOGIN PASSWORD %s',
                (target_pass,),
            )
            print(f"Created role: {target_user}")
        else:
            # Optionally update password (fails silently if no ALTER rights)
            try:
                run_sql(admin_conn, f'ALTER ROLE "{target_user}" WITH PASSWORD %s', (target_pass,))
            except Exception:
                pass
            print(f"Role exists: {target_user}")

        # 2. Create database if not exists
        if not database_exists(admin_conn, target_db):
            run_sql(admin_conn, f'CREATE DATABASE "{target_db}" OWNER "{target_user}"')
            print(f"Created database: {target_db}")
        else:
            print(f"Database exists: {target_db}")

        # 3. Grant privileges
        run_sql(admin_conn, f'GRANT ALL PRIVILEGES ON DATABASE "{target_db}" TO "{target_user}"')
        run_sql(admin_conn, f'GRANT CONNECT ON DATABASE "{target_db}" TO "{target_user}"')
        print("Granted database privileges")

        admin_conn.close()

        # 4. Connect to target database as admin: grant schema rights
        admin_params = parse_db_url(admin_url)
        ext_conn = psycopg2.connect(
            host=admin_params["host"],
            port=admin_params["port"],
            user=admin_params["user"],
            password=admin_params["password"],
            dbname=target_db,
        )
        ext_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        run_sql(ext_conn, f'GRANT ALL ON SCHEMA public TO "{target_user}"')
        print("Granted schema privileges")

        ext_conn.close()
        print("Database provisioning complete.")
        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
