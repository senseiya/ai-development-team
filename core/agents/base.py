"""Base agent interface for the AI Development Team platform."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from core.schemas import LLMResponse, ModelCapability

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all agents.

    Each agent has a capability it requests from the Model Router
    and a set of tools it can use.
    """

    name: str = "base"
    capability: ModelCapability = ModelCapability.REASONING
    tools: list[str] = []

    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's logic.

        Args:
            state: Current state of the workflow/run.

        Returns:
            Updated state after agent execution.
        """
        ...

    async def call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        router: Any | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call the LLM through the Model Router.

        In Phase 1/2, this called providers directly.
        In Phase 3, this goes through ModelRouter using the agent's capability.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            router: ModelRouter instance. If None, falls back to provider factory.
            **kwargs: Additional arguments (temperature, max_tokens, etc.).

        Returns:
            LLMResponse from the model.
        """
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
