import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import decode_access_token
from app.repos.user_repo import get_by_id

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> "User":
    from app.models.user import User

    if not credentials:
        logger.info("Auth failed: missing bearer credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        logger.info("Auth failed: invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = get_by_id(db, user_id)
    if not user:
        logger.info("Auth failed: user from token not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_user_full_access(
    user=Depends(get_current_user),
):
    """Require authenticated user who is NOT in temp password mode (must change password first)."""
    from app.repos.user_repo import is_temp_password_mode

    if is_temp_password_mode(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Change your temporary password first",
        )
    return user


def get_current_admin(
    user=Depends(get_current_user_full_access),
):
    """Require authenticated user with is_admin=True."""
    if not getattr(user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
