"""Base agent interface for the AI Development Team platform.

Every agent inherits from BaseAgent, declares its capability,
and implements run(AgentState) -> AgentState.

Phase 8: Integrates LLM cache and cost tracking.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from core.orchestrator.state import AgentState, AgentMessage
from core.schemas import LLMResponse, ModelCapability

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all agents.

    Each agent has:
    - A capability it requests from the Model Router.
    - A list of MCP tool names it may use.
    - A run() method that reads/writes AgentState.
    """

    name: str = "base"
    capability: ModelCapability = ModelCapability.REASONING
    tools: list[str] = []

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """Execute the agent's logic.

        Args:
            state: Current AgentState of the workflow/run.

        Returns:
            Updated AgentState after agent execution.
        """
        ...

    async def call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        state: AgentState | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call the LLM through the Model Router, with optional caching.

        Phase 8: Checks the LLM cache first. On miss, calls the model
        and caches the response. Also records token usage for cost tracking.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            state: Current AgentState (for router access and token tracking).
            **kwargs: Additional arguments (temperature, max_tokens, etc.).

        Returns:
            LLMResponse from the model.
        """
        # Phase 8: Try cache first (skip if temperature != 0 or caller opts out)
        use_cache = kwargs.get("use_cache", True)
        temperature = kwargs.get("temperature", 0.7)
        if use_cache and temperature == 0.0:
            try:
                from core.cost.cache import get_llm_cache

                cache = get_llm_cache()
                model_name = state.get("model_used", "") if state else ""
                cached = await cache.get(model_name, system_prompt, prompt)
                if cached is not None:
                    logger.info(
                        "Agent '%s' got cached LLM response (model=%s)",
                        self.name,
                        model_name,
                    )
                    return cached
            except Exception as e:
                logger.debug("Cache lookup failed: %s", e)

        # Call through router or fallback
        router = state.get("router") if state else None

        if router is not None:
            result = await router.call(
                capability=self.capability,
                prompt=prompt,
                system_prompt=system_prompt,
                **kwargs,
            )
            logger.info(
                "Agent '%s' used model '%s' via provider '%s' "
                "(fallback=%s, latency=%.1fms)",
                self.name,
                result.selected.model_id,
                result.selected.provider,
                result.fallback_used,
                result.response.latency_ms or 0,
            )
            response = result.response
        else:
            # Fallback to provider factory (backward compatibility)
            from core.router.providers import get_provider

            provider = get_provider()
            response = await provider.complete(
                prompt=prompt,
                system_prompt=system_prompt,
            )

        # Phase 8: Cache the response (only for deterministic calls)
        if use_cache and temperature == 0.0:
            try:
                from core.cost.cache import get_llm_cache

                cache = get_llm_cache()
                model_name = state.get("model_used", "") if state else response.model
                await cache.set(model_name, system_prompt, prompt, response)
            except Exception as e:
                logger.debug("Cache set failed: %s", e)

        return response

    def _add_message(
        self,
        state: AgentState,
        content: str,
        message_type: str = "info",
    ) -> None:
        """Append an agent message to the state.

        Args:
            state: The current AgentState (mutated in place).
            content: Message content.
            message_type: One of "info", "warning", "error", "decision".
        """
        state.setdefault("messages", []).append(
            AgentMessage(
                agent_name=self.name,
                content=content,
                message_type=message_type,
            )
        )

    def _update_tokens(
        self,
        state: AgentState,
        tokens: int,
        cost: float = 0.0,
    ) -> None:
        """Accumulate token usage and cost in the state.

        Phase 8: Also checks budget enforcement.

        Args:
            state: The current AgentState (mutated in place).
            tokens: Number of tokens to add.
            cost: Cost in USD to add.
        """
        state["tokens_used"] = state.get("tokens_used", 0) + tokens
        state["cost_usd"] = state.get("cost_usd", 0.0) + cost

        # Phase 8: Check budget
        try:
            from core.cost.budget import BudgetExceeded, check_budget, get_budget_from_state

            budget = get_budget_from_state(state)
            check_budget(
                run_id=state.get("run_id", ""),
                cost_usd=state["cost_usd"],
                tokens_used=state["tokens_used"],
                budget=budget,
            )
        except BudgetExceeded as e:
            logger.warning("Budget exceeded for run %s: %s", state.get("run_id"), e)
            state["status"] = "failed"
            state["error"] = str(e)
