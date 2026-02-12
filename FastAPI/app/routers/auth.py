import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_user_full_access
from app.config import settings
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    Token,
    UserResponse,
    UserProfileUpdate,
    ForgotPasswordRequest,
    ChangePasswordRequest,
)
from app.core.security import verify_password, create_access_token, hash_password, generate_temp_password
from app.repos.user_repo import (
    get_by_email,
    get_by_id,
    create as create_user,
    update as update_user,
    delete_user,
    set_temp_password,
    clear_temp_password,
    is_temp_password_mode,
)
from app.repos.resume_repo import get_latest_by_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
TEMP_PASSWORD_EXPIRY_MINUTES = 10


def _user_to_response(user: User, has_resume: bool) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        has_resume=has_resume,
        is_admin=getattr(user, "is_admin", False),
        requires_password_change=is_temp_password_mode(user),
    )


@router.post("/register", response_model=Token)
def register(data: UserRegister, db: Session = Depends(get_db)):
    try:
        if get_by_email(db, data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        user = create_user(db, data.email, data.password)
        logger.info("User registered: %s", user.email)
        has_resume = get_latest_by_user(db, user.id) is not None
        token = create_access_token(user.id)
        return Token(access_token=token, user=_user_to_response(user, has_resume))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Register failed for email=%s: %s", data.email, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed") from e


@router.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    try:
        user = get_by_email(db, data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )
        # Check temp password first (expires in 10 min)
        if user.temp_password_hash and user.temp_password_expires_at:
            if user.temp_password_expires_at > datetime.now(timezone.utc):
                if verify_password(data.password, user.temp_password_hash):
                    logger.info("User logged in with temp password: %s", user.email)
                    has_resume = get_latest_by_user(db, user.id) is not None
                    token = create_access_token(user.id)
                    return Token(access_token=token, user=_user_to_response(user, has_resume))
        # Normal password
        if not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        logger.info("User logged in: %s", user.email)
        has_resume = get_latest_by_user(db, user.id) is not None
        token = create_access_token(user.id)
        return Token(access_token=token, user=_user_to_response(user, has_resume))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Login failed for email=%s: %s", data.email, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed") from e


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Generate a temporary password (expires in 10 min)."""
    try:
        user = get_by_email(db, data.email)
        if not user:
            # Don't reveal whether email exists
            return {"message": "If an account exists, a temporary password has been generated. Check your email."}
        temp_pw = generate_temp_password()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=TEMP_PASSWORD_EXPIRY_MINUTES)
        set_temp_password(db, user.id, hash_password(temp_pw), expires_at)
        logger.info("Temp password generated for %s, expires in %d min", user.email, TEMP_PASSWORD_EXPIRY_MINUTES)
        if settings.expose_temp_password_in_response:
            return {
                "message": "Temporary password generated. Use it to log in, then change your password.",
                "temp_password": temp_pw,
                "expires_in_minutes": TEMP_PASSWORD_EXPIRY_MINUTES,
            }
        return {
            "message": "If an account exists, a temporary password has been generated. Check your email.",
        }
    except Exception as e:
        logger.exception("Forgot-password flow failed for email=%s: %s", data.email, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process request") from e


@router.post("/change-password", response_model=Token)
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Change password. Required when logged in with temporary password. Clears temp password after success."""
    try:
        if not is_temp_password_mode(user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use Profile to change password when logged in normally",
            )
        update_user(db, user.id, password_hash=hash_password(data.new_password))
        clear_temp_password(db, user.id)
        user = get_by_id(db, user.id)
        has_resume = get_latest_by_user(db, user.id) is not None
        token = create_access_token(user.id)
        logger.info("Password changed after temp login: %s", user.email)
        return Token(access_token=token, user=_user_to_response(user, has_resume))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Change-password failed for user=%s: %s", user.id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to change password") from e


@router.get("/me", response_model=UserResponse)
def get_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    has_resume = get_latest_by_user(db, user.id) is not None
    return _user_to_response(user, has_resume)


@router.patch("/me", response_model=UserResponse)
def update_profile(
    data: UserProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    try:
        if data.email is not None and data.email != user.email:
            if get_by_email(db, data.email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use",
                )
            update_user(db, user.id, email=data.email)

        if data.new_password is not None:
            if not verify_password(data.current_password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Current password is incorrect",
                )
            update_user(db, user.id, password_hash=hash_password(data.new_password))

        user = get_by_id(db, user.id)
        has_resume = get_latest_by_user(db, user.id) is not None
        return _user_to_response(user, has_resume)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Profile update failed for user=%s: %s", user.id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update profile") from e


@router.delete("/account")
def delete_account(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    try:
        logger.info("Account deleted: %s", user.email)
        delete_user(db, user.id)
        return {"message": "Account deleted"}
    except Exception as e:
        logger.exception("Account delete failed for user=%s: %s", user.id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete account") from e
