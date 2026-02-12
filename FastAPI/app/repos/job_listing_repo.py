import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.models.job_listing import JobListing, compute_job_hash

logger = logging.getLogger(__name__)


def batch_upsert(
    db: Session,
    rows: list[dict],
    search_category_id: str,
) -> int:
    """
    Insert job listings using ON CONFLICT (job_hash) DO NOTHING.
    Returns count of newly inserted rows.
    """
    if not rows:
        return 0
    inserted = 0
    for r in rows:
        job_hash = r.get("job_hash") or compute_job_hash(
            r.get("title", ""),
            r.get("company", ""),
            r.get("job_url", ""),
        )
        stmt = text("""
            INSERT INTO job_listings (id, job_hash, search_category_id, title, company, location, job_url, description, posted_at, extra_data)
            VALUES (:id, :job_hash, :search_category_id, :title, :company, :location, :job_url, :description, :posted_at, :extra_data)
            ON CONFLICT (job_hash) DO NOTHING
        """)
        result = db.execute(
            stmt,
            {
                "id": generate_id(),
                "job_hash": job_hash,
                "search_category_id": search_category_id,
                "title": str(r.get("title", "Unknown Title"))[:500],
                "company": str(r.get("company", "Unknown Company"))[:500],
                "location": (r.get("location") or "")[:500] if r.get("location") else None,
                "job_url": str(r.get("job_url", ""))[:2000],
                "description": (r.get("description") or "")[:50000] if r.get("description") else None,
                "posted_at": r.get("posted_at"),
                "extra_data": r.get("extra_data"),
            },
        )
        if result.rowcount and result.rowcount > 0:
            inserted += 1
    db.commit()
    logger.info("Batch upsert: %d rows inserted for category %s", inserted, search_category_id)
    return inserted


def get_jobs_by_category_since(
    db: Session,
    search_category_id: str,
    since_hours: int = 2,
) -> list[JobListing]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    return (
        db.query(JobListing)
        .filter(
            JobListing.search_category_id == search_category_id,
            JobListing.created_at >= cutoff,
        )
        .order_by(JobListing.created_at.desc())
        .all()
    )


def get_all(
    db: Session,
    search_category_id: str | None = None,
    limit: int = 200,
) -> list[JobListing]:
    """List job listings for admin. Optional filter by category."""
    q = db.query(JobListing).order_by(JobListing.created_at.desc())
    if search_category_id:
        q = q.filter(JobListing.search_category_id == search_category_id)
    return q.limit(limit).all()


def get_all_paginated(
    db: Session,
    search_category_id: str | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[JobListing], int]:
    """List job listings with optional category and title/company search. Returns (items, total)."""
    from sqlalchemy import or_
    q = db.query(JobListing).order_by(JobListing.created_at.desc())
    if search_category_id:
        q = q.filter(JobListing.search_category_id == search_category_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                JobListing.title.ilike(term),
                JobListing.company.ilike(term),
            )
        )
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return items, total


def delete_all(db: Session) -> int:
    """Delete all job listings. Returns count deleted."""
    from sqlalchemy import delete as sql_delete
    from app.models.user_job_match import UserJobMatch

    count = db.query(JobListing).count()
    # Remove dependent matches first so this works even if DB FK cascade
    # is missing/misaligned in older environments.
    db.execute(sql_delete(UserJobMatch))
    db.execute(sql_delete(JobListing))
    db.commit()
    return count


def get_by_id(db: Session, listing_id: str) -> JobListing | None:
    return db.query(JobListing).filter(JobListing.id == listing_id).first()


def create_one(
    db: Session,
    search_category_id: str,
    title: str,
    company: str,
    job_url: str,
    location: str | None = None,
    description: str | None = None,
    posted_at: str | None = None,
) -> JobListing:
    job_hash = compute_job_hash(title, company, job_url)
    listing = JobListing(
        id=generate_id(),
        job_hash=job_hash,
        search_category_id=search_category_id,
        title=(title or "Unknown Title")[:500],
        company=(company or "Unknown Company")[:500],
        location=(location or "")[:500] if location else None,
        job_url=(job_url or "")[:2000],
        description=(description or "")[:50000] if description else None,
        posted_at=posted_at,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def update_one(
    db: Session,
    listing_id: str,
    *,
    title: str | None = None,
    company: str | None = None,
    job_url: str | None = None,
    location: str | None = None,
    description: str | None = None,
    posted_at: str | None = None,
    search_category_id: str | None = None,
) -> JobListing | None:
    listing = get_by_id(db, listing_id)
    if not listing:
        return None
    if title is not None:
        listing.title = title[:500]
    if company is not None:
        listing.company = company[:500]
    if job_url is not None:
        listing.job_url = job_url[:2000]
        listing.job_hash = compute_job_hash(listing.title, listing.company, job_url)
    if location is not None:
        listing.location = location[:500] if location else None
    if description is not None:
        listing.description = description[:50000] if description else None
    if posted_at is not None:
        listing.posted_at = posted_at
    if search_category_id is not None:
        listing.search_category_id = search_category_id
    db.commit()
    db.refresh(listing)
    return listing


def delete_one(db: Session, listing_id: str) -> bool:
    from app.models.user_job_match import UserJobMatch

    listing = get_by_id(db, listing_id)
    if not listing:
        return False
    # Delete dependent rows first to avoid NOT NULL violations when ORM
    # attempts relationship synchronization during parent deletion.
    db.query(UserJobMatch).filter(UserJobMatch.job_listing_id == listing_id).delete(synchronize_session=False)
    db.delete(listing)
    db.commit()
    return True


def delete_unmatched(db: Session, min_age_hours: int = 0) -> int:
    """
    Delete job_listings that have no user_job_match (unmatched by any user).
    Optionally only delete jobs older than min_age_hours (to avoid deleting very fresh ones).
    Returns count deleted.
    """
    from app.models.user_job_match import UserJobMatch

    subq = db.query(UserJobMatch.job_listing_id).distinct().subquery()
    q = db.query(JobListing).filter(~JobListing.id.in_(subq))
    if min_age_hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=min_age_hours)
        q = q.filter(JobListing.created_at < cutoff)
    to_delete = q.all()
    count = len(to_delete)
    for j in to_delete:
        db.delete(j)
    if count > 0:
        db.commit()
        logger.info("Deleted %d unmatched job listings", count)
    return count
