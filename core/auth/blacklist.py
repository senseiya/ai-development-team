"""Redis-based token blacklist for revoked refresh tokens.

When a user logs out or refreshes their token, the old refresh token
is blacklisted in Redis with a TTL matching its remaining expiry.
"""

from __future__ import annotations

import logging

import redis.asyncio as redis

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis key prefix for blacklisted tokens
BLACKLIST_PREFIX = "token:blacklist:"


class TokenBlacklist:
    """Manages token blacklist in Redis.

    Blacklisted tokens are stored with a TTL matching their original
    expiry, so they auto-expire from Redis when no longer needed.
    """

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        """Initialize the blacklist.

        Args:
            redis_client: Optional Redis client. If None, creates one
                         from REDIS_URL in settings.
        """
        self._redis = redis_client

    async def _get_client(self) -> redis.Redis:
        """Get or create the Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
        return self._redis

    async def blacklist(self, jti: str, ttl_seconds: int) -> None:
        """Add a token JTI to the blacklist.

        Args:
            jti: The token's unique ID (JTI claim).
            ttl_seconds: Time-to-live in seconds (until token expires).
        """
        client = await self._get_client()
        key = f"{BLACKLIST_PREFIX}{jti}"
        await client.setex(key, ttl_seconds, "revoked")
        logger.debug("Blacklisted token JTI=%s for %ds", jti, ttl_seconds)

    async def is_blacklisted(self, jti: str) -> bool:
        """Check if a token JTI is blacklisted.

        Args:
            jti: The token's unique ID.

        Returns:
            True if the token has been revoked.
        """
        client = await self._get_client()
        key = f"{BLACKLIST_PREFIX}{jti}"
        return await client.exists(key) > 0

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
