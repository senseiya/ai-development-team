"""JWT token utilities for authentication.

Implements access tokens (15min) + refresh tokens (7 days)
with Redis-based blacklist for revoked refresh tokens.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from pydantic import BaseModel

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenPair(BaseModel):
    """Access + refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str
    exp: int
    iat: int
    jti: str
    token_type: str  # "access" or "refresh"


def create_access_token(user_id: str) -> str:
    """Create a short-lived access token.

    Args:
        user_id: The user's unique identifier.

    Returns:
        Encoded JWT access token.
    """
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "token_type": "access",
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token.

    Args:
        user_id: The user's unique identifier.

    Returns:
        Encoded JWT refresh token.
    """
    now = datetime.now(UTC)
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "token_type": "refresh",
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_token_pair(user_id: str) -> TokenPair:
    """Create both access and refresh tokens.

    Args:
        user_id: The user's unique identifier.

    Returns:
        TokenPair with both tokens.
    """
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


def decode_token(token: str) -> TokenPayload | None:
    """Decode and validate a JWT token.

    Args:
        token: The encoded JWT token.

    Returns:
        TokenPayload if valid, None if expired or invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenPayload(
            sub=payload["sub"],
            exp=payload["exp"],
            iat=payload["iat"],
            jti=payload["jti"],
            token_type=payload["token_type"],
        )
    except JWTError as e:
        logger.warning("Token decode failed: %s", e)
        return None


def get_token_jti(token: str) -> str | None:
    """Extract the JTI (token ID) from a token without full validation.

    Used for blacklist checks where the token might be expired.
    """
    try:
        # Decode without validation to get the JTI
        payload = jwt.get_unverified_claims(token)
        return payload.get("jti")
    except Exception:
        return None
