import logging

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import (  # noqa: F401
        SearchCategory,
        JobListing,
        User,
        Resume,
        Job,
        UserJobMatch,
    )

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized")
    except Exception as e:
        logger.exception("Database initialization failed: %s", e)
        raise


def ensure_tables_exist():
    """Create any missing tables without touching existing data."""
    from app.models import (  # noqa: F401
        SearchCategory,
        JobListing,
        User,
        Resume,
        Job,
        UserJobMatch,
    )

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        # SQLAlchemy create_all only creates missing tables, never drops existing ones.
        Base.metadata.create_all(bind=engine)
        target_tables = set(Base.metadata.tables.keys())
        created_tables = sorted(target_tables - existing_tables)

        if created_tables:
            logger.info("Created missing DB tables: %s", ", ".join(created_tables))
        else:
            logger.info("All DB tables already exist; no schema changes applied.")
    except Exception as e:
        logger.exception("Ensure tables failed: %s", e)
        raise
