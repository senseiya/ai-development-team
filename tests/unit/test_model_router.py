"""Unit tests for ModelRouter with fallback chain."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.router.model_router import ModelRouter, SelectedModel
from core.schemas import LLMResponse, ModelCapability


def _make_mock_profile(
    *,
    profile_id: str | None = None,
    provider: str = "openrouter",
    model_id: str = "test-model",
    display_name: str = "Test Model",
    capabilities: list[str] | None = None,
    cost_per_1k_input: float = 0.0,
    priority: int = 10,
    enabled: bool = True,
) -> MagicMock:
    """Create a mock ModelProfile ORM object."""
    caps = capabilities or ["code_generation"]
    profile = MagicMock()
    profile.id = profile_id or str(uuid.uuid4())
    profile.provider = provider
    profile.model_id = model_id
    profile.display_name = display_name
    profile.capabilities = json.dumps(caps)
    profile.cost_per_1k_input = cost_per_1k_input
    profile.cost_per_1k_output = 0.0
    profile.max_context = 32768
    profile.priority = priority
    profile.enabled = enabled
    return profile


def _make_mock_db(*profiles: MagicMock) -> AsyncSession:
    """Create a mock DB session returning given profiles."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = list(profiles)
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


def _make_llm_response(
    content: str = "test code",
    model: str = "test-model",
    provider: str = "openrouter",
) -> LLMResponse:
    return LLMResponse(
        content=content,
        model=model,
        provider=provider,
        tokens_used=50,
        finish_reason="stop",
        latency_ms=100.0,
    )


class TestModelRouterSelect:
    """Test ModelRouter.select() method."""

    @pytest.mark.asyncio
    async def test_select_returns_matching_capability(self) -> None:
        """Test that select returns models matching the capability."""
        profile = _make_mock_profile(
            capabilities=["code_generation"],
            priority=10,
        )
        db = _make_mock_db(profile)
        router = ModelRouter(db)

        results = await router.select(ModelCapability.CODE_GENERATION)

        assert len(results) == 1
        assert results[0].model_id == "test-model"
        assert results[0].provider == "openrouter"

    @pytest.mark.asyncio
    async def test_select_orders_by_priority(self) -> None:
        """Test that select returns models ordered by priority."""
        profile_high = _make_mock_profile(
            model_id="fast-model",
            priority=5,
        )
        profile_low = _make_mock_profile(
            model_id="slow-model",
            priority=50,
        )
        db = _make_mock_db(profile_low, profile_high)
        router = ModelRouter(db)

        results = await router.select(ModelCapability.CODE_GENERATION)

        assert len(results) == 2
        assert results[0].model_id == "fast-model"
        assert results[1].model_id == "slow-model"

    @pytest.mark.asyncio
    async def test_select_raises_on_no_match(self) -> None:
        """Test that select raises ValueError when no model matches."""
        profile = _make_mock_profile(capabilities=["reasoning"])
        db = _make_mock_db(profile)
        router = ModelRouter(db)

        with pytest.raises(ValueError, match="No enabled model found"):
            await router.select(ModelCapability.CODE_GENERATION)

    @pytest.mark.asyncio
    async def test_select_filters_by_max_cost(self) -> None:
        """Test that select filters models by max cost."""
        profile_free = _make_mock_profile(
            model_id="free-model",
            cost_per_1k_input=0.0,
            priority=10,
        )
        profile_paid = _make_mock_profile(
            model_id="paid-model",
            cost_per_1k_input=0.01,
            priority=5,
        )
        db = _make_mock_db(profile_free, profile_paid)
        router = ModelRouter(db)

        results = await router.select(
            ModelCapability.CODE_GENERATION,
            max_cost=0.0,
        )

        assert len(results) == 1
        assert results[0].model_id == "free-model"

    @pytest.mark.asyncio
    async def test_select_raises_when_cost_exceeds_all(self) -> None:
        """Test that select raises when all models exceed cost limit."""
        profile = _make_mock_profile(cost_per_1k_input=0.05)
        db = _make_mock_db(profile)
        router = ModelRouter(db)

        with pytest.raises(ValueError, match="within cost limit"):
            await router.select(
                ModelCapability.CODE_GENERATION,
                max_cost=0.01,
            )

    @pytest.mark.asyncio
    async def test_select_prefer_local(self) -> None:
        """Test that prefer_local reorders local models first."""
        profile_remote = _make_mock_profile(
            model_id="remote-model",
            provider="openrouter",
            priority=10,
        )
        profile_local = _make_mock_profile(
            model_id="local-model",
            provider="ollama",
            priority=50,
        )
        db = _make_mock_db(profile_remote, profile_local)
        router = ModelRouter(db)

        results = await router.select(
            ModelCapability.CODE_GENERATION,
            prefer_local=True,
        )

        assert len(results) == 2
        assert results[0].provider == "ollama"
        assert results[1].provider == "openrouter"


class TestModelRouterCall:
    """Test ModelRouter.call() with fallback chain."""

    @pytest.mark.asyncio
    async def test_call_returns_successful_response(self) -> None:
        """Test that call returns response from first working model."""
        profile = _make_mock_profile(model_id="good-model", priority=10)
        db = _make_mock_db(profile)
        router = ModelRouter(db)

        mock_response = _make_llm_response(model="good-model")
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        with patch(
            "core.router.model_router.get_provider",
            return_value=mock_provider,
        ):
            result = await router.call(
                capability=ModelCapability.CODE_GENERATION,
                prompt="test prompt",
            )

        assert result.response.content == "test code"
        assert result.selected.model_id == "good-model"
        assert result.fallback_used is False
        assert len(result.attempts) == 1

    @pytest.mark.asyncio
    async def test_call_uses_fallback_on_failure(self) -> None:
        """Test that call falls back to next model on failure."""
        profile_fail = _make_mock_profile(
            model_id="fail-model",
            priority=10,
        )
        profile_ok = _make_mock_profile(
            model_id="ok-model",
            priority=20,
        )
        db = _make_mock_db(profile_fail, profile_ok)
        router = ModelRouter(db)

        mock_response = _make_llm_response(model="ok-model")

        call_count = 0

        async def mock_complete(**kwargs: object) -> LLMResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Provider unavailable")
            return mock_response

        mock_provider = MagicMock()
        mock_provider.complete = mock_complete

        with patch(
            "core.router.model_router.get_provider",
            return_value=mock_provider,
        ):
            result = await router.call(
                capability=ModelCapability.CODE_GENERATION,
                prompt="test prompt",
            )

        assert result.response.model == "ok-model"
        assert result.selected.model_id == "ok-model"
        assert result.fallback_used is True
        assert len(result.attempts) == 2
        assert result.attempts[0].model_id == "fail-model"
        assert result.attempts[1].model_id == "ok-model"

    @pytest.mark.asyncio
    async def test_call_raises_when_all_models_fail(self) -> None:
        """Test that call raises RuntimeError when all models fail."""
        profile1 = _make_mock_profile(model_id="fail-1", priority=10)
        profile2 = _make_mock_profile(model_id="fail-2", priority=20)
        db = _make_mock_db(profile1, profile2)
        router = ModelRouter(db)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            side_effect=ConnectionError("All fail")
        )

        with patch(
            "core.router.model_router.get_provider",
            return_value=mock_provider,
        ), pytest.raises(RuntimeError, match="All models failed"):
            await router.call(
                capability=ModelCapability.CODE_GENERATION,
                prompt="test prompt",
            )

    @pytest.mark.asyncio
    async def test_call_logs_fallback(self) -> None:
        """Test that fallback is logged."""
        profile_fail = _make_mock_profile(
            model_id="fail-model",
            priority=10,
        )
        profile_ok = _make_mock_profile(
            model_id="ok-model",
            priority=20,
        )
        db = _make_mock_db(profile_fail, profile_ok)
        router = ModelRouter(db)

        mock_response = _make_llm_response(model="ok-model")

        call_count = 0

        async def mock_complete(**kwargs: object) -> LLMResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Unavailable")
            return mock_response

        mock_provider = MagicMock()
        mock_provider.complete = mock_complete

        with patch(
            "core.router.model_router.get_provider",
            return_value=mock_provider,
        ), patch("core.router.model_router.logger") as mock_logger:
            await router.call(
                capability=ModelCapability.CODE_GENERATION,
                prompt="test",
            )
            mock_logger.info.assert_called_once()
            assert "Fallback used" in str(
                mock_logger.info.call_args
            )


class TestSelectedModel:
    """Test SelectedModel dataclass."""

    def test_selected_model_creation(self) -> None:
        """Test creating SelectedModel instance."""
        model = SelectedModel(
            profile_id="test-id",
            provider="openrouter",
            model_id="qwen/qwen-2.5-coder-32b-instruct:free",
            display_name="Qwen 2.5 Coder 32B",
            capabilities=[ModelCapability.CODE_GENERATION],
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            max_context=32768,
            priority=10,
        )
        assert model.provider == "openrouter"
        assert model.priority == 10
        assert ModelCapability.CODE_GENERATION in model.capabilities


class TestRegistrySeed:
    """Test registry seed data."""

    @pytest.mark.asyncio
    async def test_seed_inserts_profiles(self) -> None:
        """Test that seed_model_profiles inserts seed data."""
        from core.router.registry import seed_model_profiles

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        count = await seed_model_profiles(mock_db)

        assert count == 8
        assert mock_db.add.call_count == 8
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_seed_skips_when_data_exists(self) -> None:
        """Test that seed skips if data already exists."""
        from core.router.registry import seed_model_profiles

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        count = await seed_model_profiles(mock_db)

        assert count == 0
        mock_db.add.assert_not_called()
