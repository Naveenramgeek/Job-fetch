from datetime import datetime, timezone
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session

from app.models.user_job_match import UserJobMatch
from app.models.job_listing import JobListing
from app.core.security import generate_id


def _query_matches_for_user(
    db: Session,
    user_id: str,
    status: str | None = "pending",
    search: str | None = None,
):
    from sqlalchemy import or_

    q = db.query(UserJobMatch).filter(UserJobMatch.user_id == user_id)
    q = q.join(JobListing, UserJobMatch.job_listing_id == JobListing.id)
    if status is not None:
        if status == "pending":
            q = q.filter(or_(UserJobMatch.status == "pending", UserJobMatch.status.is_(None)))
        else:
            q = q.filter(UserJobMatch.status == status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(or_(JobListing.title.ilike(term), JobListing.company.ilike(term)))
    return q


def create(
    db: Session,
    user_id: str,
    job_listing_id: str,
    match_score: float,
    match_reason: str | None = None,
    resume_years_experience: float | None = None,
) -> UserJobMatch:
    match = UserJobMatch(
        id=generate_id(),
        user_id=user_id,
        job_listing_id=job_listing_id,
        match_score=match_score,
        match_reason=match_reason,
        resume_years_experience=resume_years_experience,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def get_existing_match(db: Session, user_id: str, job_listing_id: str) -> UserJobMatch | None:
    return (
        db.query(UserJobMatch)
        .filter(
            UserJobMatch.user_id == user_id,
            UserJobMatch.job_listing_id == job_listing_id,
        )
        .first()
    )


def get_matches_for_user(
    db: Session,
    user_id: str,
    status: str | None = "pending",
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[UserJobMatch]:
    q = _query_matches_for_user(db, user_id, status=status, search=search)
    return (
        q.order_by(JobListing.created_at.desc(), UserJobMatch.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_match_count_for_user(
    db: Session,
    user_id: str,
    status: str | None = "pending",
    search: str | None = None,
) -> int:
    return _query_matches_for_user(db, user_id, status=status, search=search).count()


def get_match_for_user(db: Session, match_id: str, user_id: str) -> UserJobMatch | None:
    return (
        db.query(UserJobMatch)
        .options(joinedload(UserJobMatch.job_listing))
        .filter(UserJobMatch.id == match_id, UserJobMatch.user_id == user_id)
        .first()
    )


def delete_match(db: Session, match_id: str, user_id: str) -> bool:
    """Delete a user-job match (removes job from user's list). Returns True if deleted."""
    match = (
        db.query(UserJobMatch)
        .filter(UserJobMatch.id == match_id, UserJobMatch.user_id == user_id)
        .first()
    )
    if not match:
        return False
    db.delete(match)
    db.commit()
    return True


def update_status(
    db: Session,
    match_id: str,
    user_id: str,
    status: str,
) -> UserJobMatch | None:
    match = (
        db.query(UserJobMatch)
        .filter(UserJobMatch.id == match_id, UserJobMatch.user_id == user_id)
        .first()
    )
    if not match:
        return None
    match.status = status
    if status == "applied":
        match.applied_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(match)
    return match
