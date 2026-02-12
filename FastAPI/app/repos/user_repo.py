from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import hash_password, generate_id


def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_by_id(db: Session, user_id: str) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def create(db: Session, email: str, password: str) -> User:
    user = User(
        id=generate_id(),
        email=email,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update(
    db: Session,
    user_id: str,
    *,
    email: str | None = None,
    password_hash: str | None = None,
    search_category_id: str | None = None,
    is_admin: bool | None = None,
    is_active: bool | None = None,
) -> User | None:
    user = get_by_id(db, user_id)
    if not user:
        return None
    if email is not None:
        user.email = email
    if password_hash is not None:
        user.password_hash = password_hash
    if search_category_id is not None:
        user.search_category_id = search_category_id
    if is_admin is not None:
        user.is_admin = is_admin
    if is_active is not None:
        user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def get_all_users(db: Session) -> list[User]:
    """List all users for admin. Order by created_at desc."""
    return db.query(User).order_by(User.created_at.desc()).all()


def get_all_users_paginated(
    db: Session,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[User], int]:
    """List users with optional email search and pagination. Returns (items, total)."""
    q = db.query(User).order_by(User.created_at.desc())
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(User.email.ilike(term))
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return items, total


def get_users_by_category(db: Session, search_category_id: str) -> list[User]:
    return (
        db.query(User)
        .filter(
            User.search_category_id == search_category_id,
            User.is_active == True,
        )
        .all()
    )


def set_temp_password(
    db: Session, user_id: str, temp_password_hash: str, expires_at: datetime
) -> User | None:
    user = get_by_id(db, user_id)
    if not user:
        return None
    user.temp_password_hash = temp_password_hash
    user.temp_password_expires_at = expires_at
    db.commit()
    db.refresh(user)
    return user


def clear_temp_password(db: Session, user_id: str) -> User | None:
    user = get_by_id(db, user_id)
    if not user:
        return None
    user.temp_password_hash = None
    user.temp_password_expires_at = None
    db.commit()
    db.refresh(user)
    return user


def is_temp_password_mode(user: User) -> bool:
    """True if user is logged in with temp password (must change password)."""
    if not user.temp_password_hash or not user.temp_password_expires_at:
        return False
    return user.temp_password_expires_at > datetime.now(timezone.utc)


def delete_user(db: Session, user_id: str) -> bool:
    """Delete user and all related data (resumes, jobs via CASCADE). Returns True if deleted."""
    user = get_by_id(db, user_id)
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True
