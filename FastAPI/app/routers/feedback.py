from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_full_access
from app.models.user import User
from app.repos.feedback_repo import create_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    category: str | None = Field(default=None, max_length=120)
    message: str = Field(min_length=8, max_length=5000)
    rating: int | None = Field(default=None, ge=1, le=5)
    page: str | None = Field(default=None, max_length=500)


class FeedbackResponse(BaseModel):
    id: str
    category: str | None
    message: str
    rating: int | None
    page: str | None
    created_at: str | None


@router.post("", response_model=FeedbackResponse)
def submit_feedback(
    body: FeedbackCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    try:
        item = create_feedback(
            db,
            user_id=user.id,
            category=(body.category or "").strip() or None,
            message=body.message,
            rating=body.rating,
            page=(body.page or "").strip() or None,
        )
        return FeedbackResponse(
            id=item.id,
            category=item.category,
            message=item.message,
            rating=item.rating,
            page=item.page,
            created_at=item.created_at.isoformat() if item.created_at else None,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to submit feedback") from e
