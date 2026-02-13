import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db

logger = logging.getLogger(__name__)
from app.dependencies import get_current_user_full_access
from app.models.user import User
from app.schemas.resume import ResumeCreate, ResumeUpdate, ResumeResponse
from app.repos.resume_repo import create as create_resume, get_latest_by_user, update as update_resume
from app.repos.user_repo import get_by_id as get_user_by_id
from app.services.deep_match_service import run_deep_match_for_user
from app.services.job_collector import run_collector
from app.services.user_category_service import assign_user_category

router = APIRouter(prefix="/resumes", tags=["resumes"])
NEW_USER_BOOTSTRAP_HOURS = 10
NEW_USER_BOOTSTRAP_RESULTS = 200


def _run_new_user_bootstrap_pipeline(user_id: str) -> None:
    """
    Onboarding bootstrap: fetch broader recent jobs and immediately score for one user.
    Does not affect admin scheduler defaults (2h / 100 jobs).
    """
    db = SessionLocal()
    try:
        user = get_user_by_id(db, user_id)
        if not user or not user.search_category_id:
            logger.info("New-user bootstrap skipped: missing user/category user_id=%s", user_id)
            return
        collector = run_collector(
            db,
            category_ids=[user.search_category_id],
            results_wanted=NEW_USER_BOOTSTRAP_RESULTS,
            hours_old=NEW_USER_BOOTSTRAP_HOURS,
        )
        deep = run_deep_match_for_user(db, user_id, since_hours=NEW_USER_BOOTSTRAP_HOURS)
        logger.info("New-user bootstrap finished for user=%s: collector=%s deep_match=%s", user_id, collector, deep)
    except Exception as e:
        logger.exception("New-user bootstrap failed for user=%s: %s", user_id, e)
    finally:
        db.close()


@router.get("/latest", response_model=ResumeResponse)
def get_latest_resume(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    resume = get_latest_by_user(db, user.id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No saved resume found")
    return resume


@router.post("", response_model=ResumeResponse)
def save_resume(
    data: ResumeCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    try:
        resume = create_resume(db, user.id, data.parsed_data)
        logger.info("Resume saved for user %s", user.id)
        try:
            assigned_slug = assign_user_category(db, user.id, resume_data=data.parsed_data)
            if assigned_slug:
                background_tasks.add_task(_run_new_user_bootstrap_pipeline, user.id)
        except Exception as e:
            logger.warning("Resume saved but category assignment failed for user=%s: %s", user.id, e)
        return resume
    except Exception as e:
        logger.exception("Failed saving resume for user=%s: %s", user.id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save resume") from e


@router.put("/latest", response_model=ResumeResponse)
def update_latest_resume(
    data: ResumeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    latest = get_latest_by_user(db, user.id)
    if not latest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No saved resume to update")
    try:
        resume = update_resume(db, latest.id, user.id, data.parsed_data)
        logger.info("Resume updated for user %s", user.id)
        try:
            assign_user_category(db, user.id, resume_data=data.parsed_data)
        except Exception as e:
            logger.warning("Resume updated but category assignment failed for user=%s: %s", user.id, e)
        return resume
    except Exception as e:
        logger.exception("Failed updating resume for user=%s: %s", user.id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update resume") from e
