"""API dependencies for authentication and database access."""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from db.session import get_db

settings = get_settings()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


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
