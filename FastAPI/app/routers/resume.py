import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

logger = logging.getLogger(__name__)
from app.dependencies import get_current_user_full_access
from app.models.user import User
from app.schemas.resume import ResumeCreate, ResumeUpdate, ResumeResponse
from app.repos.resume_repo import create as create_resume, get_latest_by_user, update as update_resume
from app.services.user_category_service import assign_user_category

router = APIRouter(prefix="/resumes", tags=["resumes"])


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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    try:
        resume = create_resume(db, user.id, data.parsed_data)
        logger.info("Resume saved for user %s", user.id)
        try:
            assign_user_category(db, user.id, resume_data=data.parsed_data)
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
