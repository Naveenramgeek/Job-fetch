from sqlalchemy.orm import Session

from app.models.resume import Resume
from app.core.security import generate_id


def create(db: Session, user_id: str, parsed_data: dict) -> Resume:
    resume = Resume(
        id=generate_id(),
        user_id=user_id,
        parsed_data=parsed_data,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def get_latest_by_user(db: Session, user_id: str) -> Resume | None:
    return (
        db.query(Resume)
        .filter(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
        .first()
    )


def get_by_id(db: Session, resume_id: str, user_id: str) -> Resume | None:
    return (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == user_id)
        .first()
    )


def update(db: Session, resume_id: str, user_id: str, parsed_data: dict) -> Resume | None:
    resume = get_by_id(db, resume_id, user_id)
    if not resume:
        return None
    resume.parsed_data = parsed_data
    db.commit()
    db.refresh(resume)
    return resume
