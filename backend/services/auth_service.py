"""
Authentication primitives: password hashing + JWT encode/decode.

  - Passwords are hashed with bcrypt via passlib.
  - Tokens are signed JWTs (HS256) carrying:
      sub       = user_id
      is_guest  = bool
      iat / exp = issued-at / expiry timestamps

Used by the /auth router (issuing) and by `api/dependencies.get_current_user_id`
(verifying).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class InvalidTokenError(Exception):
    """JWT could not be decoded or has expired."""


# ---------------------------------------------------------------------------
# Password hashing — direct bcrypt usage.
#
# We intentionally do NOT go through passlib. Recent bcrypt releases (>=4.1)
# dropped the `__about__` attribute that passlib's bcrypt backend reads
# during initialization, which causes passlib.hash() to raise
# AttributeError. Talking to bcrypt directly avoids the version-detection
# dance and is just as safe — bcrypt is the actual algorithm.
# ---------------------------------------------------------------------------

# bcrypt enforces a 72-byte limit on the password (anything beyond is
# silently truncated). We truncate explicitly to keep the behaviour
# transparent.
_BCRYPT_MAX_BYTES = 72


def _to_bytes(plain: str) -> bytes:
    encoded = plain.encode("utf-8")
    return encoded[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt. Returns the UTF-8 string form."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(_to_bytes(plain), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash. Never raises."""
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(_to_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(
    *,
    sub: str,
    is_guest: bool = False,
    expires_minutes: Optional[int] = None,
) -> str:
    """Issue a signed JWT for the given user_id.

    Args:
        sub:             User identifier — becomes the `sub` claim.
        is_guest:        If True, also issues a longer-lived token by default.
        expires_minutes: Override the default expiry.
    """
    if expires_minutes is None:
        expires_minutes = (
            settings.JWT_GUEST_TOKEN_EXPIRE_MINUTES
            if is_guest
            else settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )

    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)
    payload = {
        "sub": sub,
        "is_guest": bool(is_guest),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    """Verify signature + expiry, return claims. Raises InvalidTokenError on failure."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as e:
        raise InvalidTokenError(str(e)) from e
