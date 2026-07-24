"""LLM response cache — Redis-based cache for identical prompts.

Avoids redundant LLM calls when the same prompt is sent multiple times.
Cache key is derived from a SHA-256 hash of (model, system_prompt, prompt).
TTL defaults to 1 hour.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from core.config import get_settings
from core.schemas import LLMResponse

logger = logging.getLogger(__name__)

settings = get_settings()

DEFAULT_TTL_SECONDS = 3600  # 1 hour


def _cache_key(model: str, system_prompt: str | None, prompt: str) -> str:
    """Generate a deterministic cache key from the LLM call parameters."""
    raw = f"{model}|{system_prompt or ''}|{prompt}"
    return f"llm_cache:{hashlib.sha256(raw.encode()).hexdigest()}"


class LLMCache:
    """Redis-backed LLM response cache."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds
        self._redis = None

    async def _get_redis(self) -> Any:
        """Get or create the Redis connection."""
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=2,
            )
        return self._redis

    async def get(
        self,
        model: str,
        system_prompt: str | None,
        prompt: str,
    ) -> LLMResponse | None:
        """Look up a cached LLM response.

        Args:
            model: The model identifier.
            system_prompt: The system prompt (or None).
            prompt: The user prompt.

        Returns:
            Cached LLMResponse if found, None otherwise.
        """
        try:
            redis = await self._get_redis()
            key = _cache_key(model, system_prompt, prompt)
            cached = await redis.get(key)
            if cached is None:
                return None

            data = json.loads(cached)
            logger.debug("LLM cache HIT for model=%s", model)
            return LLMResponse(**data)
        except Exception as e:
            logger.debug("LLM cache miss (error: %s)", e)
            return None

    async def set(
        self,
        model: str,
        system_prompt: str | None,
        prompt: str,
        response: LLMResponse,
    ) -> None:
        """Store an LLM response in the cache.

        Args:
            model: The model identifier.
            system_prompt: The system prompt (or None).
            prompt: The user prompt.
            response: The LLMResponse to cache.
        """
        try:
            redis = await self._get_redis()
            key = _cache_key(model, system_prompt, prompt)
            data = response.model_dump()
            await redis.set(key, json.dumps(data), ex=self.ttl_seconds)
            logger.debug("LLM cache SET for model=%s (ttl=%ds)", model, self.ttl_seconds)
        except Exception as e:
            logger.debug("LLM cache set failed: %s", e)

    async def invalidate(
        self,
        model: str,
        system_prompt: str | None,
        prompt: str,
    ) -> bool:
        """Remove a specific entry from the cache.

        Returns:
            True if the key was deleted, False otherwise.
        """
        try:
            redis = await self._get_redis()
            key = _cache_key(model, system_prompt, prompt)
            result = await redis.delete(key)
            return result > 0
        except Exception:
            return False

    async def clear_all(self) -> int:
        """Clear all LLM cache entries.

        Returns:
            Number of keys deleted.
        """
        try:
            redis = await self._get_redis()
            keys: list[str] = []
            async for key in redis.scan_iter("llm_cache:*"):
                keys.append(key)
            if keys:
                return await redis.delete(*keys)
            return 0
        except Exception:
            return 0

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with hit_count, miss_count, and key_count.
        """
        try:
            redis = await self._get_redis()
            key_count = 0
            async for _ in redis.scan_iter("llm_cache:*"):
                key_count += 1
            return {"key_count": key_count}
        except Exception:
            return {"key_count": 0}

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None


# Singleton instance
_llm_cache: LLMCache | None = None


def get_llm_cache() -> LLMCache:
    """Get the singleton LLMCache instance."""
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = LLMCache()
    return _llm_cache
