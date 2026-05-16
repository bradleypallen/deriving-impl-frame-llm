"""Provider abstraction: Anthropic, OpenAI, OpenRouter, mock.

Each concrete provider satisfies the :class:`Provider` Protocol in
:mod:`infereval.providers.base`. Use :func:`get_provider` to construct
one by name; SDK imports are lazy so users only pay the cost of the
backends they actually use.
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseProvider,
    Provider,
    ProviderConfigError,
    ProviderError,
    ProviderSampleError,
    RetryPolicy,
    SampleRequest,
    SampleResult,
)


def get_provider(provider: str, model_id: str, **kwargs: Any) -> Provider:
    """Construct a provider by short name.

    Parameters
    ----------
    provider
        Provider short name: ``"anthropic"``, ``"openai"``, ``"openrouter"``, or ``"mock"``.
    model_id
        Provider-specific model identifier.
    **kwargs
        Passed through to the concrete provider's constructor (e.g.
        ``api_key``, ``base_url``, ``retry_policy``, ``http_referer``).

    Returns
    -------
    Provider
        A constructed provider instance satisfying the :class:`Provider`
        Protocol.

    Raises
    ------
    ProviderConfigError
        If ``provider`` is not a known short name or required configuration is
        missing (e.g. API key not set, optional SDK not installed).
    """
    normalized = provider.strip().lower()
    if normalized == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(model_id, **kwargs)
    if normalized == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider(model_id, **kwargs)
    if normalized == "openrouter":
        from .openrouter import OpenRouterProvider

        return OpenRouterProvider(model_id, **kwargs)
    if normalized == "mock":
        from .mock import ScriptedProvider

        return ScriptedProvider(model_id=model_id, **kwargs)
    raise ProviderConfigError(
        f"Unknown provider {provider!r}. "
        "Supported: 'anthropic', 'openai', 'openrouter', 'mock'."
    )


__all__ = [
    "BaseProvider",
    "Provider",
    "ProviderConfigError",
    "ProviderError",
    "ProviderSampleError",
    "RetryPolicy",
    "SampleRequest",
    "SampleResult",
    "get_provider",
]
