"""Automatic model router with capability-based selection and fallback."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.router.providers import get_provider
from core.schemas import LLMResponse, ModelCapability

logger = logging.getLogger(__name__)


@dataclass
class SelectedModel:
    """Result of a model selection by the router."""

    profile_id: str
    provider: str
    model_id: str
    display_name: str
    capabilities: list[ModelCapability]
    cost_per_1k_input: float
    cost_per_1k_output: float
    max_context: int
    priority: int


@dataclass
class RouterResult:
    """Complete result of a router call including fallback attempts."""

    selected: SelectedModel
    response: LLMResponse
    attempts: list[SelectedModel] = field(default_factory=list)
    fallback_used: bool = False


class ModelRouter:
    """Routes LLM requests to the best model based on capability.

    Models are loaded from the database (model_profiles table) and
    ordered by priority. The router tries models in priority order,
    falling back to the next one on failure.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._profiles_cache: list[dict] | None = None

    async def _load_profiles(self) -> list[dict]:
        """Load all enabled model profiles from database."""
        from db.models import ModelProfile

        result = await self._db.execute(select(ModelProfile).where(ModelProfile.enabled.is_(True)))
        rows = result.scalars().all()

        profiles = []
        for row in rows:
            caps = json.loads(row.capabilities)
            profiles.append(
                {
                    "id": row.id,
                    "provider": row.provider,
                    "model_id": row.model_id,
                    "display_name": row.display_name,
                    "capabilities": [ModelCapability(c) for c in caps],
                    "cost_per_1k_input": row.cost_per_1k_input,
                    "cost_per_1k_output": row.cost_per_1k_output,
                    "max_context": row.max_context,
                    "priority": row.priority,
                }
            )

        profiles.sort(key=lambda p: p["priority"])
        return profiles

    async def select(
        self,
        capability: ModelCapability,
        max_cost: float | None = None,
        prefer_local: bool = False,
    ) -> list[SelectedModel]:
        """Select models matching the capability, ordered for fallback.

        Args:
            capability: The capability required (e.g. CODE_GENERATION).
            max_cost: Optional maximum cost per 1k input tokens.
            prefer_local: If True, prefer Ollama models when available.

        Returns:
            Ordered list of SelectedModel candidates for fallback chain.

        Raises:
            ValueError: If no model matches the capability.
        """
        profiles = await self._load_profiles()

        matching = [p for p in profiles if capability in p["capabilities"]]

        if not matching:
            raise ValueError(f"No enabled model found for capability: {capability.value}")

        if max_cost is not None:
            matching = [p for p in matching if p["cost_per_1k_input"] <= max_cost]

            if not matching:
                raise ValueError(
                    f"No model for '{capability.value}' within cost limit {max_cost}/1k tokens"
                )

        if prefer_local:
            local = [p for p in matching if p["provider"] == "ollama"]
            remote = [p for p in matching if p["provider"] != "ollama"]
            matching = local + remote

        return [
            SelectedModel(
                profile_id=p["id"],
                provider=p["provider"],
                model_id=p["model_id"],
                display_name=p["display_name"],
                capabilities=p["capabilities"],
                cost_per_1k_input=p["cost_per_1k_input"],
                cost_per_1k_output=p["cost_per_1k_output"],
                max_context=p["max_context"],
                priority=p["priority"],
            )
            for p in matching
        ]

    async def call(
        self,
        capability: ModelCapability,
        prompt: str,
        system_prompt: str | None = None,
        max_cost: float | None = None,
        prefer_local: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> RouterResult:
        """Select a model and call it, with automatic fallback.

        Args:
            capability: The capability required.
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            max_cost: Optional max cost constraint.
            prefer_local: Prefer local models.
            temperature: Sampling temperature.
            max_tokens: Max tokens in response.

        Returns:
            RouterResult with the successful response and metadata.

        Raises:
            RuntimeError: If all models in the fallback chain fail.
        """
        candidates = await self.select(
            capability=capability,
            max_cost=max_cost,
            prefer_local=prefer_local,
        )

        last_error: Exception | None = None
        attempts: list[SelectedModel] = []

        for candidate in candidates:
            attempts.append(candidate)
            try:
                provider = get_provider(candidate.provider)
                response = await provider.complete(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                fallback_used = len(attempts) > 1
                if fallback_used:
                    logger.info(
                        "Fallback used: %s -> %s",
                        attempts[0].model_id,
                        candidate.model_id,
                    )

                return RouterResult(
                    selected=candidate,
                    response=response,
                    attempts=attempts,
                    fallback_used=fallback_used,
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    "Model %s failed: %s. Trying next...",
                    candidate.model_id,
                    str(e),
                )
                continue

        raise RuntimeError(
            f"All models failed for capability '{capability.value}'. "
            f"Attempts: {[a.model_id for a in attempts]}. "
            f"Last error: {last_error}"
        )
