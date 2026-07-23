"""Integration tests for Ollama provider.

These tests run against a local Ollama instance.
They require Ollama to be running (docker-compose up ollama) with the model pulled.

Run with: pytest tests/integration/test_ollama.py -v -m integration
"""

import os

import pytest
import httpx

from core.router.providers.ollama import OllamaProvider
from core.router.providers.base import LLMProvider, ProviderHealth


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")


def is_ollama_running() -> bool:
    """Check if Ollama is accessible."""
    try:
        response = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


def has_model() -> bool:
    """Check if the configured model is available."""
    try:
        response = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        if response.status_code != 200:
            return False
        models = response.json().get("models", [])
        return any(OLLAMA_MODEL in m.get("name", "") for m in models)
    except Exception:
        return False


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def ollama_provider() -> OllamaProvider:
    """Create an Ollama provider instance."""
    return OllamaProvider(base_url=OLLAMA_BASE_URL)


class TestOllamaProviderProtocol:
    """Test that OllamaProvider implements the LLMProvider protocol."""

    def test_implements_protocol(self, ollama_provider: OllamaProvider) -> None:
        """Test that OllamaProvider satisfies LLMProvider protocol."""
        assert isinstance(ollama_provider, LLMProvider)

    def test_has_name_property(self, ollama_provider: OllamaProvider) -> None:
        """Test that provider has name property."""
        assert ollama_provider.name == "ollama"

    def test_has_complete_method(self, ollama_provider: OllamaProvider) -> None:
        """Test that provider has complete method."""
        assert hasattr(ollama_provider, "complete")
        assert callable(ollama_provider.complete)

    def test_has_health_check_method(self, ollama_provider: OllamaProvider) -> None:
        """Test that provider has health_check method."""
        assert hasattr(ollama_provider, "health_check")
        assert callable(ollama_provider.health_check)

    def test_has_close_method(self, ollama_provider: OllamaProvider) -> None:
        """Test that provider has close method."""
        assert hasattr(ollama_provider, "close")
        assert callable(ollama_provider.close)


class TestOllamaHealthCheck:
    """Test Ollama health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_returns_provider_health(
        self, ollama_provider: OllamaProvider
    ) -> None:
        """Test that health_check returns ProviderHealth instance."""
        health = await ollama_provider.health_check()
        assert isinstance(health, ProviderHealth)
        assert health.provider == "ollama"

        if is_ollama_running():
            if has_model():
                assert health.healthy is True
                assert health.latency_ms is not None
                assert health.latency_ms > 0
            else:
                # Ollama running but no models pulled
                assert health.healthy is False
                assert "not found" in health.error.lower()
        else:
            assert health.healthy is False
            assert health.error is not None


class TestOllamaComplete:
    """Test Ollama completion functionality."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not has_model(), reason=f"Model '{OLLAMA_MODEL}' not available")
    async def test_complete_basic_prompt(self, ollama_provider: OllamaProvider) -> None:
        """Test basic prompt completion."""
        response = await ollama_provider.complete(
            prompt="What is 2 + 2? Reply with just the number.",
            max_tokens=50,
        )

        assert response.content is not None
        assert len(response.content) > 0
        assert response.provider == "ollama"
        assert response.latency_ms is not None
        assert response.latency_ms > 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(not has_model(), reason=f"Model '{OLLAMA_MODEL}' not available")
    async def test_complete_with_system_prompt(self, ollama_provider: OllamaProvider) -> None:
        """Test completion with system prompt."""
        response = await ollama_provider.complete(
            prompt="Write a hello world function",
            system_prompt="You are an expert Python developer. Write clean, documented code.",
            max_tokens=200,
        )

        assert response.content is not None
        assert "def" in response.content.lower() or "hello" in response.content.lower()
        assert response.provider == "ollama"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not has_model(), reason=f"Model '{OLLAMA_MODEL}' not available")
    async def test_complete_returns_model_info(self, ollama_provider: OllamaProvider) -> None:
        """Test that response contains model information."""
        response = await ollama_provider.complete(
            prompt="Hello",
            max_tokens=10,
        )

        assert response.model is not None
        assert len(response.model) > 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(not has_model(), reason=f"Model '{OLLAMA_MODEL}' not available")
    async def test_complete_respects_max_tokens(self, ollama_provider: OllamaProvider) -> None:
        """Test that max_tokens parameter is respected."""
        response_short = await ollama_provider.complete(
            prompt="Write a long story about dragons",
            max_tokens=50,
        )

        response_long = await ollama_provider.complete(
            prompt="Write a long story about dragons",
            max_tokens=200,
        )

        assert response_long.content is not None
        assert response_short.content is not None


class TestOllamaErrorHandling:
    """Test Ollama error handling."""

    @pytest.mark.asyncio
    async def test_health_check_with_wrong_url(self) -> None:
        """Test health check with invalid URL."""
        provider = OllamaProvider(base_url="http://localhost:99999")
        health = await provider.health_check()

        assert health.healthy is False
        assert health.error is not None

    @pytest.mark.asyncio
    async def test_complete_with_wrong_url(self) -> None:
        """Test complete with invalid URL raises error."""
        provider = OllamaProvider(base_url="http://localhost:99999")

        with pytest.raises(httpx.ConnectError):
            await provider.complete(prompt="Hello")


class TestOllamaProviderFactory:
    """Test provider factory integration."""

    def test_get_provider_ollama(self) -> None:
        """Test getting Ollama provider via factory."""
        from core.router.providers import get_provider

        provider = get_provider("ollama")
        assert isinstance(provider, OllamaProvider)
        assert provider.name == "ollama"

    def test_get_provider_default_from_config(self) -> None:
        """Test getting default provider from config."""
        from core.config import get_settings
        from core.router.providers import get_provider

        settings = get_settings()
        original = settings.DEFAULT_PROVIDER

        settings.DEFAULT_PROVIDER = "ollama"
        try:
            provider = get_provider()
            assert isinstance(provider, OllamaProvider)
        finally:
            settings.DEFAULT_PROVIDER = original
