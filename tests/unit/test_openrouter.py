"""Unit tests for the OpenRouter provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.router.providers.openrouter import OpenRouterProvider
from core.schemas import LLMResponse


@pytest.mark.unit
class TestOpenRouterProvider:
    """Tests for OpenRouterProvider class."""

    @pytest.fixture
    def provider(self) -> OpenRouterProvider:
        """Create a provider instance for testing."""
        return OpenRouterProvider(
            api_key="test-key",
            base_url="https://test.openrouter.ai/api/v1",
            model="test-model",
        )

    @pytest.mark.asyncio
    async def test_complete_returns_response(self, provider: OpenRouterProvider) -> None:
        """Test that complete() returns a valid LLMResponse."""
        mock_response_data = {
            "choices": [
                {
                    "message": {"content": "def hello(): pass"},
                    "finish_reason": "stop",
                }
            ],
            "model": "test-model",
            "usage": {"total_tokens": 25},
        }

        mock_response_http = MagicMock()
        mock_response_http.json.return_value = mock_response_data
        mock_response_http.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response_http)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.complete("Write a hello function")

            assert isinstance(result, LLMResponse)
            assert result.content == "def hello(): pass"
            assert result.model == "test-model"
            assert result.tokens_used == 25

    @pytest.mark.asyncio
    async def test_complete_includes_system_prompt(self, provider: OpenRouterProvider) -> None:
        """Test that system prompt is included in messages."""
        mock_response_data = {
            "choices": [{"message": {"content": "test"}, "finish_reason": "stop"}],
            "model": "test-model",
            "usage": {"total_tokens": 10},
        }

        mock_response_http = MagicMock()
        mock_response_http.json.return_value = mock_response_data
        mock_response_http.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response_http)

        with patch.object(provider, "_get_client", return_value=mock_client):
            await provider.complete("test", system_prompt="You are a coder")

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
            messages = payload["messages"]

            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_complete_without_system_prompt(self, provider: OpenRouterProvider) -> None:
        """Test that completion works without system prompt."""
        mock_response_data = {
            "choices": [{"message": {"content": "test"}, "finish_reason": "stop"}],
            "model": "test-model",
            "usage": {"total_tokens": 10},
        }

        mock_response_http = MagicMock()
        mock_response_http.json.return_value = mock_response_data
        mock_response_http.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response_http)

        with patch.object(provider, "_get_client", return_value=mock_client):
            await provider.complete("test")

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
            messages = payload["messages"]

            assert len(messages) == 1
            assert messages[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_close_cleans_up_client(self, provider: OpenRouterProvider) -> None:
        """Test that close() cleans up the HTTP client."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        provider._client = mock_client

        await provider.close()

        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_skips_if_already_closed(self, provider: OpenRouterProvider) -> None:
        """Test that close() skips if client is already closed."""
        mock_client = AsyncMock()
        mock_client.is_closed = True
        provider._client = mock_client

        await provider.close()

        mock_client.aclose.assert_not_called()
