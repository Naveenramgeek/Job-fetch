import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db, ensure_tables_exist
from app.dependencies import get_current_admin
from app.models.user import User
from app.repos.admin_repo import get_stats
from app.repos.user_repo import get_all_users, get_all_users_paginated, get_by_id, create as create_user_repo, update as update_user, delete_user
from app.repos.search_category_repo import seed_default_categories, get_all as get_all_categories
from app.repos.job_listing_repo import (
    get_all_paginated as get_job_listings_paginated,
    get_by_id as get_job_listing_by_id,
    create_one as create_job_listing,
    update_one as update_job_listing,
    delete_one as delete_job_listing,
    delete_all as delete_all_job_listings,
)
from app.core.security import hash_password
from app.models.job_listing import JobListing
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str
    is_admin: bool = False
    is_active: bool = True
    search_category_id: str | None = None


class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    is_admin: bool | None = None
    is_active: bool | None = None
    search_category_id: str | None = None


class AdminJobListingCreate(BaseModel):
    search_category_id: str
    title: str
    company: str
    job_url: str
    location: str | None = None
    description: str | None = None
    posted_at: str | None = None


class AdminJobListingUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    job_url: str | None = None
    location: str | None = None
    description: str | None = None
    posted_at: str | None = None
    search_category_id: str | None = None


router = APIRouter(prefix="/admin", tags=["admin"])


def _user_to_response(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "is_active": u.is_active,
        "is_admin": getattr(u, "is_admin", False),
        "search_category_id": u.search_category_id,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _job_listing_to_response(j: JobListing) -> dict:
    return {
        "id": j.id,
        "job_hash": j.job_hash,
        "search_category_id": j.search_category_id,
        "title": j.title,
        "company": j.company,
        "location": j.location,
        "job_url": j.job_url,
        "description": (j.description or "")[:500] if j.description else None,
        "posted_at": j.posted_at,
        "created_at": j.created_at.isoformat() if j.created_at else None,
    }


@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    """Return dashboard stats. Admin only."""
    try:
        return get_stats(db)
    except Exception as e:
        logger.exception("Admin stats failed for admin=%s: %s", user.email, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load admin stats") from e


@router.get("/users")
def list_users(
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    """List users with optional email search and pagination. Admin only."""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size
    users, total = get_all_users_paginated(db, search=search, limit=page_size, offset=offset)
    return {"items": [_user_to_response(u) for u in users], "total": total}


@router.get("/users/{user_id}")
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Get one user by id. Admin only."""
    target = get_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_to_response(target)


@router.post("/users")
def create_user_admin(
    body: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Create a user. Admin only."""
    from app.repos.user_repo import get_by_email
    from app.repos.search_category_repo import get_by_id as get_category_by_id
    if get_by_email(db, body.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    if body.search_category_id and not get_category_by_id(db, body.search_category_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid search_category_id")
    user = create_user_repo(db, body.email, body.password)
    update_user(
        db,
        user.id,
        is_admin=body.is_admin,
        is_active=body.is_active,
        search_category_id=body.search_category_id,
    )
    return _user_to_response(get_by_id(db, user.id))


@router.patch("/users/{user_id}")
def update_user_admin(
    user_id: str,
    body: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Update user. Admin only. Cannot demote self from admin."""
    from app.repos.user_repo import get_by_email
    from app.repos.search_category_repo import get_by_id as get_category_by_id
    target = get_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if target.id == current_user.id and body.is_admin is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin status",
        )
    if body.email:
        other = get_by_email(db, body.email)
        if other and other.id != user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")
    if body.search_category_id is not None and body.search_category_id and not get_category_by_id(db, body.search_category_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid search_category_id")
    password_hash = hash_password(body.password) if body.password else None
    updated = update_user(
        db,
        user_id,
        email=body.email,
        password_hash=password_hash,
        is_admin=body.is_admin,
        is_active=body.is_active,
        search_category_id=body.search_category_id,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_to_response(updated)


@router.delete("/users/{user_id}")
def delete_user_admin(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Delete a user. Admin only. Cannot delete self."""
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")
    if not get_by_id(db, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not delete_user(db, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"message": "User deleted"}


@router.get("/categories")
def list_categories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    """List all search categories for admin (e.g. dropdowns). Admin only."""
    categories = get_all_categories(db)
    return [{"id": c.id, "slug": c.slug, "display_name": c.display_name} for c in categories]


@router.post("/seed-categories")
def seed_categories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    """Seed default search categories if table is empty. Admin only."""
    ensure_tables_exist()
    categories, created_count = seed_default_categories(db)
    if created_count:
        message = f"Created {created_count} default categories."
    else:
        message = f"Categories already exist ({len(categories)} categories)."
    return {"message": message, "categories": [{"slug": c.slug, "display_name": c.display_name} for c in categories]}


# ---- Job listings (scraped jobs) CRUD ----
@router.get("/job-listings")
def list_job_listings(
    search_category_id: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    """List job listings with optional category and title/company search, pagination. Admin only."""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size
    listings, total = get_job_listings_paginated(
        db,
        search_category_id=search_category_id,
        search=search,
        limit=page_size,
        offset=offset,
    )
    return {"items": [_job_listing_to_response(j) for j in listings], "total": total}


@router.get("/job-listings/{listing_id}")
def get_job_listing(
    listing_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    """Get one job listing. Admin only."""
    j = get_job_listing_by_id(db, listing_id)
    if not j:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job listing not found")
    out = _job_listing_to_response(j)
    out["description"] = j.description  # full description for edit
    return out


@router.post("/job-listings")
def create_job_listing_admin(
    body: AdminJobListingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    """Create a job listing. Admin only."""
    from app.repos.search_category_repo import get_by_id as get_category_by_id
    if not get_category_by_id(db, body.search_category_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid search_category_id")
    j = create_job_listing(
        db,
        search_category_id=body.search_category_id,
        title=body.title,
        company=body.company,
        job_url=body.job_url,
        location=body.location,
        description=body.description,
        posted_at=body.posted_at,
    )
    return _job_listing_to_response(j)


@router.patch("/job-listings/{listing_id}")
def update_job_listing_admin(
    listing_id: str,
    body: AdminJobListingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    """Update a job listing. Admin only."""
    updated = update_job_listing(
        db,
        listing_id,
        title=body.title,
        company=body.company,
        job_url=body.job_url,
        location=body.location,
        description=body.description,
        posted_at=body.posted_at,
        search_category_id=body.search_category_id,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job listing not found")
    return _job_listing_to_response(updated)


@router.delete("/job-listings")
def delete_all_job_listings_admin(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    """Delete all job listings. Admin only."""
    deleted = delete_all_job_listings(db)
    logger.info("Admin %s deleted all job listings: %d", user.email, deleted)
    return {"message": f"Deleted {deleted} job listings", "deleted": deleted}


@router.delete("/job-listings/{listing_id}")
def delete_job_listing_admin(
    listing_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    """Delete a job listing. Admin only."""
    if not delete_job_listing(db, listing_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job listing not found")
    return {"message": "Job listing deleted"}
