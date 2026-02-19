import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_user_full_access
from app.config import settings
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    Token,
    RegisterMessage,
    UserResponse,
    UserProfileUpdate,
    ForgotPasswordRequest,
    ChangePasswordRequest,
    ResetPasswordRequest,
)
from app.core.security import (
    verify_password,
    create_access_token,
    create_email_action_token,
    decode_email_action_token,
    hash_password,
)
from app.repos.user_repo import (
    get_by_email,
    get_by_id,
    create as create_user,
    update as update_user,
    delete_user,
    clear_temp_password,
    is_temp_password_mode,
)
from app.repos.resume_repo import get_latest_by_user
from app.models.user import User
from app.services.email_service import send_activation_email, send_reset_password_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
ACTIVATE_ACCOUNT_ACTION = "activate_account"
RESET_PASSWORD_ACTION = "reset_password"


def _user_to_response(user: User, has_resume: bool) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        has_resume=has_resume,
        is_admin=getattr(user, "is_admin", False),
        requires_password_change=is_temp_password_mode(user),
    )


def _build_activation_link(token: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/auth/activate?token={token}"


def _build_reset_password_link(token: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/auth/reset-password?token={token}"


@router.post("/register", response_model=Token | RegisterMessage)
def register(data: UserRegister, db: Session = Depends(get_db)):
    try:
        if get_by_email(db, data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        user = create_user(db, data.email, data.password)
        if settings.require_email_activation:
            update_user(db, user.id, is_active=False)
            activation_token = create_email_action_token(
                user.id,
                action=ACTIVATE_ACCOUNT_ACTION,
                expires_minutes=settings.activation_token_expire_minutes,
            )
            send_activation_email(to_email=user.email, activation_link=_build_activation_link(activation_token))
            logger.info("Activation email triggered for newly registered user: %s", user.email)
            return RegisterMessage(message="Registration successful. Please check your email to activate your account.")
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
                detail="Account is inactive. Please activate your account from your email.",
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


@router.get("/activate", response_model=Token)
def activate_account(token: str, db: Session = Depends(get_db)):
    """Activate a registered account using one-time email link."""
    user_id = decode_email_action_token(token, expected_action=ACTIVATE_ACCOUNT_ACTION)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired activation link")
    user = get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not user.is_active:
        update_user(db, user.id, is_active=True)
        user = get_by_id(db, user.id)
        logger.info("User activated via email link: %s", user.email)

    has_resume = get_latest_by_user(db, user.id) is not None
    access_token = create_access_token(user.id)
    return Token(access_token=access_token, user=_user_to_response(user, has_resume))


@router.post("/resend-activation", response_model=RegisterMessage)
def resend_activation(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Resend activation email for inactive users. Response is always generic."""
    user = get_by_email(db, data.email)
    if user and not user.is_active:
        activation_token = create_email_action_token(
            user.id,
            action=ACTIVATE_ACCOUNT_ACTION,
            expires_minutes=settings.activation_token_expire_minutes,
        )
        send_activation_email(to_email=user.email, activation_link=_build_activation_link(activation_token))
        logger.info("Activation email re-sent for user: %s", user.email)
    return RegisterMessage(message="If an inactive account exists, an activation email has been sent.")


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Send password reset link email if account exists."""
    try:
        user = get_by_email(db, data.email)
        if user:
            reset_token = create_email_action_token(
                user.id,
                action=RESET_PASSWORD_ACTION,
                expires_minutes=settings.reset_password_token_expire_minutes,
            )
            send_reset_password_email(to_email=user.email, reset_link=_build_reset_password_link(reset_token))
            logger.info("Password reset email triggered for %s", user.email)
        return {
            "message": "If an account exists, a password reset link has been sent to email.",
        }
    except Exception as e:
        logger.exception("Forgot-password flow failed for email=%s: %s", data.email, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process request") from e


@router.post("/reset-password", response_model=RegisterMessage)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using token from email link."""
    try:
        user_id = decode_email_action_token(data.token, expected_action=RESET_PASSWORD_ACTION)
        if not user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link")
        user = get_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        update_user(db, user.id, password_hash=hash_password(data.new_password))
        clear_temp_password(db, user.id)
        logger.info("Password reset completed via email link for user=%s", user.email)
        return RegisterMessage(message="Password updated successfully. You can now sign in.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Reset-password flow failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reset password") from e


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
