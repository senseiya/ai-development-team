"""Tests for cost optimization — tracker, budget, cache, and endpoints."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.cost.budget import (
    BudgetConfig,
    BudgetExceeded,
    check_budget,
    get_budget_from_state,
)
from core.cost.tracker import (
    RunCostSummary,
    TokenUsage,
    calculate_cost,
    calculate_cost_sync,
    clear_cost_cache,
)
from core.cost.cache import LLMCache, _cache_key, get_llm_cache
from core.schemas import LLMResponse


class TestCostCalculation:
    def test_calculate_cost_zero_tokens(self) -> None:
        """Zero tokens should yield zero cost."""
        cost = calculate_cost(0, 0, 0.001, 0.002)
        assert cost == 0.0

    def test_calculate_cost_input_only(self) -> None:
        """Only input tokens."""
        cost = calculate_cost(1000, 0, 0.001, 0.002)
        assert cost == pytest.approx(0.001, abs=1e-8)

    def test_calculate_cost_output_only(self) -> None:
        """Only output tokens."""
        cost = calculate_cost(0, 1000, 0.001, 0.002)
        assert cost == pytest.approx(0.002, abs=1e-8)

    def test_calculate_cost_both(self) -> None:
        """Both input and output tokens."""
        cost = calculate_cost(2000, 3000, 0.001, 0.002)
        expected = (2000 / 1000) * 0.001 + (3000 / 1000) * 0.002
        assert cost == pytest.approx(expected, abs=1e-8)

    def test_calculate_cost_sync_uses_cache(self) -> None:
        """calculate_cost_sync should use the in-memory cost cache."""
        from core.cost.tracker import _cost_cache

        _cost_cache["test_provider/test_model"] = (0.005, 0.01)
        cost = calculate_cost_sync(1000, 1000, "test_provider", "test_model")
        assert cost == pytest.approx(0.015, abs=1e-8)
        _cost_cache.clear()

    def test_calculate_cost_sync_unknown_model(self) -> None:
        """Unknown model should default to 0.0 cost."""
        cost = calculate_cost_sync(1000, 1000, "unknown", "model")
        assert cost == 0.0

    def test_clear_cost_cache(self) -> None:
        """clear_cost_cache should empty the cache."""
        from core.cost.tracker import _cost_cache

        _cost_cache["key"] = (0.1, 0.2)
        clear_cost_cache()
        assert len(_cost_cache) == 0


class TestBudgetEnforcement:
    def test_within_budget(self) -> None:
        """No exception when within budget."""
        budget = BudgetConfig(max_cost_usd=1.0, max_tokens=100_000)
        result = check_budget("run-1", 0.5, 50_000, budget)
        assert result is True

    def test_cost_exceeded(self) -> None:
        """BudgetExceeded raised when cost exceeds limit."""
        budget = BudgetConfig(max_cost_usd=0.1, max_tokens=100_000)
        with pytest.raises(BudgetExceeded, match="cost"):
            check_budget("run-2", 0.5, 1000, budget)

    def test_tokens_exceeded(self) -> None:
        """BudgetExceeded raised when tokens exceed limit."""
        budget = BudgetConfig(max_cost_usd=10.0, max_tokens=1000)
        with pytest.raises(BudgetExceeded, match="tokens"):
            check_budget("run-3", 0.01, 5000, budget)

    def test_get_budget_from_state(self) -> None:
        """Budget should be extracted from state dict."""
        state = {"budget_max_cost_usd": 5.0, "budget_max_tokens": 50_000}
        budget = get_budget_from_state(state)
        assert budget.max_cost_usd == 5.0
        assert budget.max_tokens == 50_000

    def test_get_budget_defaults(self) -> None:
        """Missing keys should use defaults."""
        budget = get_budget_from_state({})
        assert budget.max_cost_usd == 1.0
        assert budget.max_tokens == 100_000

    def test_budget_exceeded_exception_attributes(self) -> None:
        """BudgetExceeded should carry useful attributes."""
        exc = BudgetExceeded("run-x", "cost", 0.5, 0.1)
        assert exc.run_id == "run-x"
        assert exc.reason == "cost"
        assert exc.current == 0.5
        assert exc.limit == 0.1


class TestLLMCache:
    def test_cache_key_deterministic(self) -> None:
        """Same inputs should produce the same cache key."""
        k1 = _cache_key("model-a", "system", "prompt")
        k2 = _cache_key("model-a", "system", "prompt")
        assert k1 == k2

    def test_cache_key_varies_by_model(self) -> None:
        """Different models should produce different keys."""
        k1 = _cache_key("model-a", None, "prompt")
        k2 = _cache_key("model-b", None, "prompt")
        assert k1 != k2

    def test_cache_key_varies_by_prompt(self) -> None:
        """Different prompts should produce different keys."""
        k1 = _cache_key("model-a", None, "prompt1")
        k2 = _cache_key("model-a", None, "prompt2")
        assert k1 != k2

    @pytest.mark.asyncio
    async def test_cache_miss_on_empty(self) -> None:
        """Cache should return None on empty Redis."""
        cache = LLMCache()
        with patch.object(cache, "_get_redis", new_callable=AsyncMock) as mock_redis:
            mock_redis.return_value = AsyncMock()
            mock_redis.return_value.get = AsyncMock(return_value=None)
            result = await cache.get("model", None, "prompt")
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self) -> None:
        """Cache should store and retrieve LLM responses."""
        cache = LLMCache()
        response = LLMResponse(content="hello", model="m", tokens_used=10)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        with patch.object(cache, "_get_redis", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_redis
            await cache.set("model", None, "prompt", response)

            # Now retrieve
            import json
            cached_data = response.model_dump()
            mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))
            result = await cache.get("model", None, "prompt")
            assert result is not None
            assert result.content == "hello"
            assert result.tokens_used == 10

    @pytest.mark.asyncio
    async def test_cache_clear_all(self) -> None:
        """clear_all should delete all llm_cache:* keys."""
        cache = LLMCache()
        mock_redis = AsyncMock()

        async def fake_scan_iter(match: str):
            for key in ["llm_cache:abc", "llm_cache:def"]:
                yield key

        mock_redis.scan_iter = fake_scan_iter
        mock_redis.delete = AsyncMock(return_value=2)

        with patch.object(cache, "_get_redis", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_redis
            count = await cache.clear_all()
            assert count == 2

    @pytest.mark.asyncio
    async def test_cache_stats(self) -> None:
        """stats should return key count."""
        cache = LLMCache()
        mock_redis = AsyncMock()

        async def fake_scan_iter(match: str):
            for _ in range(3):
                yield "llm_cache:x"

        mock_redis.scan_iter = fake_scan_iter

        with patch.object(cache, "_get_redis", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_redis
            stats = await cache.stats()
            assert stats["key_count"] == 3


class TestCostEndpoints:
    def test_cost_summary_endpoint(self) -> None:
        """GET /api/v1/costs/summary should return 200."""
        from unittest.mock import AsyncMock, MagicMock

        from apps.api.deps import get_db_session
        from apps.api.main import app

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.one.return_value = (0, 0)
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db_session] = lambda: mock_db
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/api/v1/costs/summary",
                headers={"X-API-Key": "change-me-in-production"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "total_runs" in data
            assert "total_tokens" in data
        finally:
            app.dependency_overrides.clear()

    def test_run_cost_endpoint_not_found(self) -> None:
        """GET /api/v1/costs/runs/{id} should return 404 for unknown run."""
        from unittest.mock import AsyncMock, MagicMock

        from apps.api.deps import get_db_session
        from apps.api.main import app

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db_session] = lambda: mock_db
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/api/v1/costs/runs/nonexistent",
                headers={"X-API-Key": "change-me-in-production"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()
