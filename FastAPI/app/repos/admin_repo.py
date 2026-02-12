"""Admin-specific repository functions for stats and system data."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.job_listing import JobListing
from app.models.user_job_match import UserJobMatch
from app.models.search_category import SearchCategory


def get_stats(db: Session) -> dict:
    """Return admin dashboard stats."""
    user_count = db.query(func.count(User.id)).scalar() or 0
    active_user_count = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    job_listing_count = db.query(func.count(JobListing.id)).scalar() or 0
    job_match_count = db.query(func.count(UserJobMatch.id)).scalar() or 0
    category_count = db.query(func.count(SearchCategory.id)).scalar() or 0
    admin_count = db.query(func.count(User.id)).filter(User.is_admin == True).scalar() or 0
    return {
        "users_total": user_count,
        "users_active": active_user_count,
        "job_listings": job_listing_count,
        "user_job_matches": job_match_count,
        "categories": category_count,
        "admins": admin_count,
    }
