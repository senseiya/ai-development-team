"""Budget enforcement — limits cost and tokens per run.

If a run exceeds its budget, the pipeline is aborted with a budget_exceeded status.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BudgetConfig:
    """Budget limits for a run."""

    max_cost_usd: float = 1.0
    max_tokens: int = 100_000


# Default budgets (can be overridden per-run via state)
DEFAULT_BUDGET = BudgetConfig()


class BudgetExceededError(Exception):
    """Raised when a run exceeds its budget."""

    def __init__(self, run_id: str, reason: str, current: float, limit: float) -> None:
        self.run_id = run_id
        self.reason = reason
        self.current = current
        self.limit = limit
        super().__init__(
            f"Budget exceeded for run {run_id}: {reason} ({current:.6f} > {limit:.6f})"
        )


# Compatibility alias
BudgetExceeded = BudgetExceededError


def check_budget(
    run_id: str,
    cost_usd: float,
    tokens_used: int,
    budget: BudgetConfig | None = None,
) -> bool:
    """Check if the run is within budget.

    Args:
        run_id: The run identifier.
        cost_usd: Current cumulative cost in USD.
        tokens_used: Current cumulative token count.
        budget: Budget limits (uses DEFAULT_BUDGET if None).

    Returns:
        True if within budget, False if exceeded.

    Raises:
        BudgetExceededError: If budget is exceeded (also logs the event).
    """
    if budget is None:
        budget = DEFAULT_BUDGET

    if cost_usd > budget.max_cost_usd:
        logger.warning(
            "Budget exceeded: cost $%.6f > $%.6f for run %s",
            cost_usd,
            budget.max_cost_usd,
            run_id,
        )
        raise BudgetExceeded(
            run_id=run_id,
            reason="cost",
            current=cost_usd,
            limit=budget.max_cost_usd,
        )

    if tokens_used > budget.max_tokens:
        logger.warning(
            "Budget exceeded: %d tokens > %d limit for run %s",
            tokens_used,
            budget.max_tokens,
            run_id,
        )
        raise BudgetExceeded(
            run_id=run_id,
            reason="tokens",
            current=float(tokens_used),
            limit=float(budget.max_tokens),
        )

    return True


def get_budget_from_state(state: dict) -> BudgetConfig:
    """Extract budget configuration from AgentState.

    Looks for 'budget_max_cost_usd' and 'budget_max_tokens' keys.
    Falls back to DEFAULT_BUDGET for missing values.
    """
    return BudgetConfig(
        max_cost_usd=state.get("budget_max_cost_usd", DEFAULT_BUDGET.max_cost_usd),
        max_tokens=state.get("budget_max_tokens", DEFAULT_BUDGET.max_tokens),
    )
