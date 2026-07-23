"""Base agent interface for the AI Development Team platform."""

from abc import ABC, abstractmethod
from typing import Any

from core.schemas import LLMResponse, ModelCapability


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
        provider: Any | None = None,
    ) -> LLMResponse:
        """Call the LLM with the given prompt.

        In Phase 1, this called OpenRouter directly.
        In Phase 2, this uses the provider factory based on DEFAULT_PROVIDER config.
        In Phase 3, this will go through the ModelRouter.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            provider: LLM provider instance (uses factory if None).

        Returns:
            LLMResponse from the model.
        """
        if provider is None:
            from core.router.providers import get_provider

            provider = get_provider()

        return await provider.complete(
            prompt=prompt,
            system_prompt=system_prompt,
        )
