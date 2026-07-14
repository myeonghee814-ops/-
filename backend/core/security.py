"""Authentication placeholders: password hashing and JWT helpers.

Nothing in this module is wired to an endpoint yet -- there is no signup,
login, or route that requires a caller to be authenticated. This exists so
the pieces a real auth flow needs (hash a password, verify it, mint and
read a bearer token) are already written, tested, and ready to be adopted
without redesigning the primitives under time pressure later.

Uses `bcrypt` directly rather than `passlib` -- passlib is effectively
unmaintained and its version-detection code breaks against current
`bcrypt` releases (it expects a `bcrypt.__about__` attribute recent
`bcrypt` versions no longer provide).
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Mint a JWT bearer token for `subject` (intended to be a user ID)."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Return the token's subject if valid, else None (expired, malformed,
    or signed with a different key)."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    return payload.get("sub")
