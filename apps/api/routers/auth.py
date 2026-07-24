"""Authentication router - JWT login, register, refresh, logout.

Phase 9: Rate limited (10 req/min) to prevent brute-force attacks.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db_session
from core.auth.blacklist import TokenBlacklist
from core.auth.tokens import (
    TokenPair,
    create_token_pair,
    decode_token,
    get_token_jti,
)
from core.config import get_settings
from db.models import User

settings = get_settings()
router = APIRouter()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["10/minute"],
    storage_uri="memory://",
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Schemas ---


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """User login request."""

    username: str
    password: str


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Token logout request."""

    refresh_token: str


class UserResponse(BaseModel):
    """User info response."""

    id: str
    email: str
    username: str
    is_admin: bool

    model_config = {"from_attributes": True}


# --- Helpers ---


def _hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain, hashed)


# --- Endpoints ---


@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
@limiter.limit("10/minute")
async def register(
    request: Request,
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Register a new user account.

    Args:
        req: Registration data (email, username, password).
        db: Database session.

    Returns:
        UserResponse with the created user.

    Raises:
        HTTPException: If email or username already exists.
    """
    # Check for existing user
    result = await db.execute(
        select(User).where(
            (User.email == req.email) | (User.username == req.username)
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        detail = "Email already registered" if existing.email == req.email else "Username taken"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )

    user = User(
        id=str(uuid.uuid4()),
        email=req.email,
        username=req.username,
        hashed_password=_hash_password(req.password),
        is_active=True,
        is_admin=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()

    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        is_admin=user.is_admin,
    )


@router.post(
    "/auth/login",
    response_model=TokenPair,
    summary="Login and get tokens",
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    req: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenPair:
    """Authenticate and return access + refresh tokens.

    Args:
        req: Login credentials.
        db: Database session.

    Returns:
        TokenPair with access and refresh tokens.

    Raises:
        HTTPException: If credentials are invalid.
    """
    result = await db.execute(
        select(User).where(User.username == req.username)
    )
    user = result.scalar_one_or_none()

    if not user or not _verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return create_token_pair(user.id)


@router.post(
    "/auth/refresh",
    response_model=TokenPair,
    summary="Refresh access token",
)
async def refresh_token(
    req: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenPair:
    """Exchange a refresh token for a new token pair.

    The old refresh token is blacklisted in Redis.

    Args:
        req: Contains the refresh token.
        db: Database session.

    Returns:
        New TokenPair.

    Raises:
        HTTPException: If refresh token is invalid or blacklisted.
    """
    payload = decode_token(req.refresh_token)

    if not payload or payload.token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Check blacklist
    blacklist = TokenBlacklist()
    jti = get_token_jti(req.refresh_token)
    if jti and await blacklist.is_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    # Blacklist the old refresh token
    if jti:
        from datetime import timedelta

        from core.auth.tokens import REFRESH_TOKEN_EXPIRE_DAYS

        ttl = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).seconds
        await blacklist.blacklist(jti, ttl)

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == payload.sub))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    return create_token_pair(user.id)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout (blacklist refresh token)",
)
async def logout(
    req: LogoutRequest,
) -> None:
    """Blacklist a refresh token to invalidate it.

    Args:
        req: Contains the refresh token to blacklist.
    """
    blacklist = TokenBlacklist()
    jti = get_token_jti(req.refresh_token)
    if jti:
        from datetime import timedelta

        from core.auth.tokens import REFRESH_TOKEN_EXPIRE_DAYS

        ttl = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).seconds
        await blacklist.blacklist(jti, ttl)
