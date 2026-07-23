"""Ollama LLM provider implementation for local models."""

from typing import Any

import httpx

from core.config import get_settings
from core.schemas import LLMResponse

settings = get_settings()

# Ollama-specific timeouts (local process, should be fast)
OLLAMA_TIMEOUT_CONNECT = 5.0
OLLAMA_TIMEOUT_READ = 300.0  # Local inference can be slow for large models
OLLAMA_TIMEOUT_WRITE = 5.0


class OllamaProvider:
    """Ollama API client for local LLM completions."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        """Provider name."""
        return "ollama"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Content-Type": "application/json"},
                timeout=httpx.Timeout(
                    connect=OLLAMA_TIMEOUT_CONNECT,
                    read=OLLAMA_TIMEOUT_READ,
                    write=OLLAMA_TIMEOUT_WRITE,
                    pool=OLLAMA_TIMEOUT_CONNECT,
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
        """Send a completion request to Ollama.

        Uses the /api/chat endpoint for chat-style completions.

        Args:
            prompt: The user prompt/query.
            system_prompt: Optional system prompt for context.
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens in the response (mapped to num_predict).

        Returns:
            LLMResponse with the model's output.

        Raises:
            httpx.HTTPStatusError: If the API returns an error.
            httpx.ConnectError: If Ollama is not running.
            httpx.TimeoutException: If inference takes too long.
        """
        import time

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        client = await self._get_client()
        start_time = time.monotonic()
        response = await client.post("/api/chat", json=payload)
        latency_ms = (time.monotonic() - start_time) * 1000
        response.raise_for_status()

        data = response.json()
        message = data.get("message", {})
        # Ollama doesn't always return token counts; estimate from eval_count
        tokens_used = data.get("eval_count", 0) or data.get("prompt_eval_count", 0)

        return LLMResponse(
            content=message.get("content", ""),
            model=data.get("model", self.model),
            provider=self.name,
            tokens_used=tokens_used,
            finish_reason="stop" if data.get("done") else None,
            latency_ms=latency_ms,
        )

    async def health_check(self) -> "ProviderHealth":
        """Check if Ollama is running and the model is available.

        Returns:
            ProviderHealth with connection status and model info.
        """
        from core.router.providers.base import ProviderHealth

        import time

        try:
            client = await self._get_client()
            start_time = time.monotonic()
            response = await client.get("/api/tags")
            latency_ms = (time.monotonic() - start_time) * 1000
            response.raise_for_status()

            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            model_available = any(self.model in m for m in models)

            if not model_available:
                return ProviderHealth(
                    provider=self.name,
                    healthy=False,
                    error=f"Model '{self.model}' not found. Available: {models}",
                    latency_ms=latency_ms,
                )

            return ProviderHealth(
                provider=self.name,
                healthy=True,
                latency_ms=latency_ms,
            )
        except httpx.ConnectError:
            return ProviderHealth(
                provider=self.name,
                healthy=False,
                error="Cannot connect to Ollama. Is it running?",
            )
        except Exception as e:
            return ProviderHealth(
                provider=self.name,
                healthy=False,
                error=str(e),
            )

    async def pull_model(self) -> bool:
        """Pull/download the configured model if not present.

        Returns:
            True if model was pulled successfully or already present.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/pull",
                json={"name": self.model, "stream": False},
            )
            response.raise_for_status()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
