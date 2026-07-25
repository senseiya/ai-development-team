"""Unit tests for LLM provider protocol and factory."""

import pytest

from core.router.providers import get_provider, list_providers
from core.router.providers.base import LLMProvider, ProviderHealth
from core.schemas import LLMResponse


class TestLLMProviderProtocol:
    """Test the LLMProvider protocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that LLMProvider is runtime_checkable."""
        assert hasattr(LLMProvider, "__protocol_attrs__") or callable(
            getattr(LLMProvider, "__instancecheck__", None)
        )

    def test_mock_satisfies_protocol(self) -> None:
        """Test that a mock implementing the protocol is recognized."""

        class MockProvider:
            @property
            def name(self) -> str:
                return "mock"

            async def complete(
                self,
                prompt: str,
                system_prompt: str | None = None,
                temperature: float = 0.7,
                max_tokens: int = 4096,
            ) -> LLMResponse:
                return LLMResponse(content="test", model="mock")

            async def health_check(self) -> ProviderHealth:
                return ProviderHealth(provider="mock", healthy=True)

            async def close(self) -> None:
                pass

        provider = MockProvider()
        assert isinstance(provider, LLMProvider)


class TestProviderFactory:
    """Test the provider factory function."""

    def test_get_openrouter_provider(self) -> None:
        """Test getting OpenRouter provider."""
        from core.router.providers.openrouter import OpenRouterProvider

        provider = get_provider("openrouter")
        assert isinstance(provider, OpenRouterProvider)
        assert provider.name == "openrouter"

    def test_get_unknown_provider_raises(self) -> None:
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("unknown_provider")

    def test_list_providers(self) -> None:
        """Test listing available providers."""
        providers = list_providers()
        assert "openrouter" in providers
        assert len(providers) == 1


class TestProviderHealth:
    """Test ProviderHealth model."""

    def test_provider_health_creation(self) -> None:
        """Test creating ProviderHealth instance."""
        health = ProviderHealth(
            provider="test",
            healthy=True,
            latency_ms=100.5,
        )
        assert health.provider == "test"
        assert health.healthy is True
        assert health.latency_ms == 100.5
        assert health.error is None

    def test_provider_health_with_error(self) -> None:
        """Test creating ProviderHealth with error."""
        health = ProviderHealth(
            provider="test",
            healthy=False,
            error="Connection refused",
        )
        assert health.healthy is False
        assert health.error == "Connection refused"
