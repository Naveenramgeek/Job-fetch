from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.models.feedback import Feedback
from app.models.user import User


def create_feedback(
    db: Session,
    *,
    user_id: str,
    category: str | None,
    message: str,
    rating: int | None,
    page: str | None,
) -> Feedback:
    item = Feedback(
        id=generate_id(),
        user_id=user_id,
        category=category or None,
        message=message.strip(),
        rating=rating,
        page=page or None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_feedback_paginated(
    db: Session,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[Feedback, User]], int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size

    q = db.query(Feedback, User).join(User, User.id == Feedback.user_id).order_by(Feedback.created_at.desc())
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(
            User.email.ilike(term) | Feedback.message.ilike(term) | Feedback.category.ilike(term)
        )
    total = q.count()
    items = q.offset(offset).limit(page_size).all()
    return items, total
