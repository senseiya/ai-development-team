"""LLM provider factory and registry."""

from typing import Any

from core.config import get_settings
from core.router.providers.base import LLMProvider
from core.router.providers.openrouter import OpenRouterProvider


def get_provider(
    provider_name: str | None = None,
    **kwargs: Any,
) -> LLMProvider:
    """Get an LLM provider instance by name.

    Args:
        provider_name: Provider name. Only 'openrouter' is supported.
            If None, uses DEFAULT_PROVIDER from config.
        **kwargs: Additional arguments passed to the provider constructor.

    Returns:
        An instance of the requested LLMProvider.

    Raises:
        ValueError: If provider_name is not recognized.
    """
    settings = get_settings()
    name = provider_name or settings.DEFAULT_PROVIDER

    if name == "openrouter":
        return OpenRouterProvider(**kwargs)
    else:
        raise ValueError(
            f"Unknown provider: '{name}'. Only 'openrouter' is supported."
        )


def list_providers() -> list[str]:
    """List all available provider names.

    Returns:
        List of provider names.
    """
    return ["openrouter"]
