"""Password hashing and session cookie signing (session-based auth for MVP)."""
import base64
import hmac
import hashlib
import time
from typing import Any

from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# Session token: base64(user_id:timestamp).hmac
def _sign_payload(payload: bytes) -> str:
    settings = get_settings()
    sig = hmac.new(
        settings.secret_key.encode("utf-8") if isinstance(settings.secret_key, str) else settings.secret_key,
        payload,
        hashlib.sha256,
    ).hexdigest()
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=") + "." + sig


def _verify_sig(payload: bytes, sig: str) -> bool:
    settings = get_settings()
    expected = hmac.new(
        settings.secret_key.encode("utf-8") if isinstance(settings.secret_key, str) else settings.secret_key,
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


def create_session_token(user_id: int) -> str:
    """Create a signed session token for the user (for auth cookie)."""
    ts = int(time.time())
    payload = f"{user_id}:{ts}".encode("utf-8")
    return _sign_payload(payload)


def verify_session_token(token: str) -> int | None:
    """Verify signed token and return user_id if valid; None otherwise."""
    if not token or "." not in token:
        return None
    try:
        encoded, sig = token.rsplit(".", 1)
        pad = 4 - len(encoded) % 4
        if pad != 4:
            encoded += "=" * pad
        payload = base64.urlsafe_b64decode(encoded)
        if not _verify_sig(payload, sig):
            return None
        parts = payload.decode("utf-8").split(":", 1)
        user_id = int(parts[0])
        ts = int(parts[1])
        # Optional: expire after 14 days
        if abs(time.time() - ts) > 14 * 24 * 3600:
            return None
        return user_id
    except (ValueError, IndexError):
        return None


# JWT helpers kept for optional future use
def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {"sub": str(subject), "exp": expire, "type": "access"}
    if extra:
        to_encode.update(extra)
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    from jose import JWTError, jwt
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
