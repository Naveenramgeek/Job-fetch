import hashlib
import secrets
import string
from datetime import datetime, timedelta
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def _prehash(password: str) -> bytes:
    """Pre-hash to avoid bcrypt's 72-byte limit."""
    return hashlib.sha256(password.encode()).digest()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_prehash(plain), hashed.encode())


def create_access_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_email_action_token(subject: str, action: str, expires_minutes: int) -> str:
    """Create short-lived token for email actions like account activation."""
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode = {"sub": subject, "exp": expire, "action": action}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_email_action_token(token: str, expected_action: str) -> str | None:
    """Decode action token and return subject only if action matches."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("action") != expected_action:
            return None
        return payload.get("sub")
    except JWTError:
        return None


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def generate_id() -> str:
    return str(uuid4())


def generate_temp_password(length: int = 12) -> str:
    """Generate a random temporary password (alphanumeric + a few symbols)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
