"""Base agent interface for the AI Development Team platform.

Every agent inherits from BaseAgent, declares its capability,
and implements run(AgentState) -> AgentState.
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
        """Call the LLM through the Model Router.

        The router is read from state["router"]. If no router is
        available, falls back to the provider factory.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            state: Current AgentState (for router access and token tracking).
            **kwargs: Additional arguments (temperature, max_tokens, etc.).

        Returns:
            LLMResponse from the model.
        """
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
            return result.response

        # Fallback to provider factory (backward compatibility)
        from core.router.providers import get_provider

        provider = get_provider()
        return await provider.complete(
            prompt=prompt,
            system_prompt=system_prompt,
        )

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

        Args:
            state: The current AgentState (mutated in place).
            tokens: Number of tokens to add.
            cost: Cost in USD to add.
        """
        state["tokens_used"] = state.get("tokens_used", 0) + tokens
        state["cost_usd"] = state.get("cost_usd", 0.0) + cost
