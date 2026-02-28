"""JWT creation and verification using python-jose."""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from jose import JWTError, jwt

from pbam.config import get_settings


def _settings():
    return get_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: UUID) -> tuple[str, str, datetime]:
    """Create a signed JWT access token.

    Returns:
        (token_string, jti, expires_at)
    """
    settings = _settings()
    jti = str(uuid4())
    expires_at = _utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": jti,
        "iat": _utcnow(),
        "exp": expires_at,
        "type": "access",
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token. Raises JWTError on failure."""
    settings = _settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])


def hash_jti(jti: str) -> str:
    """SHA-256 hash of the JWT ID for secure storage."""
    return hashlib.sha256(jti.encode()).hexdigest()


def get_user_id_from_token(token: str) -> UUID:
    """Extract user_id from a valid token or raise JWTError."""
    payload = decode_access_token(token)
    return UUID(payload["sub"])


def get_jti_from_token(token: str) -> str:
    """Extract raw jti from a valid token."""
    payload = decode_access_token(token)
    return payload["jti"]
