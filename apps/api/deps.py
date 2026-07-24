"""API dependencies for authentication and database access.

Supports both:
- Static API key (X-API-Key header) — backward compatibility
- JWT Bearer token (Authorization: Bearer <token>) — new auth
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.blacklist import TokenBlacklist
from core.auth.tokens import decode_token, get_token_jti
from core.config import get_settings
from db.session import get_db

settings = get_settings()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    """Verify the API key from the request header.

    Args:
        api_key: The API key from X-API-Key header.

    Returns:
        The validated API key.

    Raises:
        HTTPException: If the API key is invalid or missing.
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
        )

    if api_key != settings.API_KEY_STATIC:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return api_key


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    api_key: str | None = Security(api_key_header),
) -> str:
    """Get the current user ID from either JWT or API key.

    Priority:
    1. JWT Bearer token (returns user_id from token)
    2. Static API key (returns "api-key-user" as fallback)

    Args:
        credentials: Optional Bearer token.
        api_key: Optional API key.

    Returns:
        User ID string.

    Raises:
        HTTPException: If neither valid JWT nor API key is provided.
    """
    # Try JWT first
    if credentials and credentials.credentials:
        payload = decode_token(credentials.credentials)
        if payload and payload.token_type == "access":
            # Check blacklist
            blacklist = TokenBlacklist()
            jti = get_token_jti(credentials.credentials)
            if jti and await blacklist.is_blacklisted(jti):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                )
            return payload.sub

    # Fallback to API key
    if api_key and api_key == settings.API_KEY_STATIC:
        return "api-key-user"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication. Provide Bearer token or X-API-Key.",
    )


async def get_db_session(
    db: AsyncSession = Depends(get_db),
) -> AsyncSession:  # type: ignore[misc]
    """Get a database session dependency.

    Args:
        db: Database session from get_db.

    Returns:
        The database session.
    """
    return db
