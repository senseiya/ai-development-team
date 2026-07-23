"""Base LLM provider protocol and shared types."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ProviderHealth(BaseModel):
    """Health status of an LLM provider."""

    provider: str
    healthy: bool
    latency_ms: float | None = None
    error: str | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol that all LLM providers must implement.

    This ensures a common interface between OpenRouter, Ollama,
    and any future providers.
    """

    @property
    def name(self) -> str:
        """Unique provider name (e.g., 'openrouter', 'ollama')."""
        ...

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> "LLMResponse":
        """Send a completion request to the provider.

        Args:
            prompt: The user prompt/query.
            system_prompt: Optional system prompt for context.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            LLMResponse with the model's output.
        """
        ...

    async def health_check(self) -> ProviderHealth:
        """Check if the provider is reachable and responding.

        Returns:
            ProviderHealth with status information.
        """
        ...

    async def close(self) -> None:
        """Clean up resources (HTTP clients, connections, etc.)."""
        ...


# Avoid circular import at module level
from core.schemas import LLMResponse  # noqa: E402
