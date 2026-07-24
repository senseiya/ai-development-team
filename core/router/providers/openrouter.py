"""OpenRouter LLM provider implementation."""

from typing import Any

import httpx

from core.config import get_settings
from core.schemas import LLMResponse

settings = get_settings()

# OpenRouter-specific timeouts (remote API, network-dependent)
OPENROUTER_TIMEOUT_CONNECT = 10.0
OPENROUTER_TIMEOUT_READ = 120.0
OPENROUTER_TIMEOUT_WRITE = 10.0


class OpenRouterProvider:
    """OpenRouter API client for LLM completions."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.base_url = base_url or settings.OPENROUTER_BASE_URL
        self.model = model or settings.OPENROUTER_MODEL
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        """Provider name."""
        return "openrouter"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://ai-development-team.local",
                    "X-Title": "AI Development Team",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(
                    connect=OPENROUTER_TIMEOUT_CONNECT,
                    read=OPENROUTER_TIMEOUT_READ,
                    write=OPENROUTER_TIMEOUT_WRITE,
                    pool=OPENROUTER_TIMEOUT_CONNECT,
                ),
            )
        return self._client

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a completion request to OpenRouter.

        Args:
            prompt: The user prompt/query.
            system_prompt: Optional system prompt for context.
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            LLMResponse with the model's output.

        Raises:
            httpx.HTTPStatusError: If the API returns an error.
            httpx.ConnectError: If connection fails.
            httpx.TimeoutException: If request times out.
        """
        import time

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        client = await self._get_client()
        start_time = time.monotonic()
        response = await client.post("/chat/completions", json=payload)
        latency_ms = (time.monotonic() - start_time) * 1000
        response.raise_for_status()

        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", self.model),
            provider=self.name,
            tokens_used=usage.get("total_tokens", 0),
            finish_reason=choice.get("finish_reason"),
            latency_ms=latency_ms,
        )

    async def health_check(self) -> "ProviderHealth":
        """Check if OpenRouter is reachable.

        Returns:
            ProviderHealth with connection status.
        """
        import time

        from core.router.providers.base import ProviderHealth

        try:
            client = await self._get_client()
            start_time = time.monotonic()
            response = await client.get("/models")
            latency_ms = (time.monotonic() - start_time) * 1000
            response.raise_for_status()
            return ProviderHealth(
                provider=self.name,
                healthy=True,
                latency_ms=latency_ms,
            )
        except Exception as e:
            return ProviderHealth(
                provider=self.name,
                healthy=False,
                error=str(e),
            )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
