"""Cost tracker — calculates USD costs from token counts and model pricing.

Reads cost_per_1k_input and cost_per_1k_output from the ModelProfile table
and computes actual cost for each LLM call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ModelProfile

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Record of a single LLM call's token usage and cost."""

    agent: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RunCostSummary:
    """Aggregated cost summary for a single run."""

    run_id: str
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    breakdown: list[TokenUsage] = field(default_factory=list)


# In-memory cost cache for quick lookups (model_id → costs)
_cost_cache: dict[str, tuple[float, float]] = {}


def _cache_key(provider: str, model_id: str) -> str:
    return f"{provider}/{model_id}"


async def get_model_costs(
    db: AsyncSession,
    provider: str,
    model_id: str,
) -> tuple[float, float]:
    """Look up cost_per_1k_input and cost_per_1k_output for a model.

    Uses an in-memory cache to avoid repeated DB queries.

    Returns:
        Tuple of (cost_per_1k_input, cost_per_1k_output).
    """
    key = _cache_key(provider, model_id)
    if key in _cost_cache:
        return _cost_cache[key]

    result = await db.execute(
        select(ModelProfile).where(
            ModelProfile.provider == provider,
            ModelProfile.model_id == model_id,
        )
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        # Unknown model — assume free
        costs = (0.0, 0.0)
    else:
        costs = (profile.cost_per_1k_input, profile.cost_per_1k_output)

    _cost_cache[key] = costs
    return costs


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    cost_per_1k_input: float,
    cost_per_1k_output: float,
) -> float:
    """Calculate the USD cost for a given token usage.

    Args:
        input_tokens: Number of input (prompt) tokens.
        output_tokens: Number of output (completion) tokens.
        cost_per_1k_input: Cost per 1000 input tokens in USD.
        cost_per_1k_output: Cost per 1000 output tokens in USD.

    Returns:
        Total cost in USD.
    """
    input_cost = (input_tokens / 1000.0) * cost_per_1k_input
    output_cost = (output_tokens / 1000.0) * cost_per_1k_output
    return round(input_cost + output_cost, 8)


def calculate_cost_sync(
    input_tokens: int,
    output_tokens: int,
    provider: str = "",
    model_id: str = "",
) -> float:
    """Calculate cost using cached or default pricing (sync, no DB).

    Falls back to 0.0 for unknown models.
    """
    key = _cache_key(provider, model_id) if provider and model_id else ""
    costs = _cost_cache.get(key, (0.0, 0.0))
    return calculate_cost(input_tokens, output_tokens, costs[0], costs[1])


def clear_cost_cache() -> None:
    """Clear the in-memory cost cache."""
    _cost_cache.clear()
