"""Cost optimization package — tracker, budget enforcement, and LLM cache."""

from core.cost.budget import BudgetConfig, BudgetExceededError, check_budget, get_budget_from_state
from core.cost.cache import LLMCache, get_llm_cache
from core.cost.tracker import (
    RunCostSummary,
    TokenUsage,
    calculate_cost,
    calculate_cost_sync,
    clear_cost_cache,
    get_model_costs,
)

# Compat alias
BudgetExceeded = BudgetExceededError

__all__ = [
    "BudgetConfig",
    "BudgetExceededError",
    "BudgetExceeded",
    "LLMCache",
    "RunCostSummary",
    "TokenUsage",
    "calculate_cost",
    "calculate_cost_sync",
    "check_budget",
    "clear_cost_cache",
    "get_budget_from_state",
    "get_llm_cache",
    "get_model_costs",
]
