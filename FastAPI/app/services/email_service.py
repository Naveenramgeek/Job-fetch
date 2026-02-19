import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _has_mailgun_config() -> bool:
    return bool(settings.mailgun_api_key and settings.mailgun_domain and settings.mailgun_from_email)


def send_email(*, to_email: str, subject: str, text: str) -> bool:
    """
    Send email via Mailgun if configured.
    Returns True when provider accepted request, False otherwise.
    """
    if not _has_mailgun_config():
        logger.warning("Mailgun not configured. Skipping email send to=%s subject=%s", to_email, subject)
        return False

    url = f"https://api.mailgun.net/v3/{settings.mailgun_domain}/messages"
    try:
        response = httpx.post(
            url,
            auth=("api", settings.mailgun_api_key or ""),
            data={
                "from": settings.mailgun_from_email,
                "to": [to_email],
                "subject": subject,
                "text": text,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.warning("Mailgun send failed to=%s subject=%s err=%s", to_email, subject, e)
        return False


def send_activation_email(*, to_email: str, activation_link: str) -> bool:
    subject = "Activate your JobFetch account"
    text = (
        "Welcome to JobFetch!\n\n"
        "Please activate your account by clicking the link below:\n"
        f"{activation_link}\n\n"
        f"This link expires in {settings.activation_token_expire_minutes} minutes.\n\n"
        "If you did not create this account, you can ignore this email."
    )
    return send_email(to_email=to_email, subject=subject, text=text)


def send_reset_password_email(*, to_email: str, reset_link: str) -> bool:
    subject = "Reset your JobFetch password"
    text = (
        "We received a request to reset your JobFetch password.\n\n"
        "Use the link below to set a new password:\n"
        f"{reset_link}\n\n"
        f"This link expires in {settings.reset_password_token_expire_minutes} minutes.\n\n"
        "If you didn't request this, you can ignore this email."
    )
    return send_email(to_email=to_email, subject=subject, text=text)
