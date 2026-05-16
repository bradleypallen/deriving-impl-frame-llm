"""OpenRouter provider.

OpenRouter is OpenAI-API-compatible; this provider is a thin subclass of
:class:`OpenAIProvider` overriding the base URL and the API-key environment
variable, with optional ``HTTP-Referer`` and ``X-Title`` headers used by
OpenRouter for attribution.

The ``openai`` SDK is the only dependency: ``pip install 'infereval[openai]'``.
"""

from __future__ import annotations

import random

from .base import RetryPolicy
from .openai import OpenAIProvider

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter backend reached via the OpenAI Chat Completions client.

    Parameters
    ----------
    model_id
        OpenRouter model identifier, e.g. ``"anthropic/claude-3.5-sonnet"``.
    http_referer
        Optional ``HTTP-Referer`` header value, recommended by OpenRouter
        for application attribution.
    x_title
        Optional ``X-Title`` header value, also for attribution.
    """

    name = "openrouter"
    DEFAULT_BASE_URL = OPENROUTER_DEFAULT_BASE_URL
    API_KEY_ENV = OPENROUTER_API_KEY_ENV

    def __init__(
        self,
        model_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        http_referer: str | None = None,
        x_title: str | None = None,
        retry_policy: RetryPolicy | None = None,
        rng: random.Random | None = None,
    ) -> None:
        headers: dict[str, str] = {}
        if http_referer:
            headers["HTTP-Referer"] = http_referer
        if x_title:
            headers["X-Title"] = x_title
        super().__init__(
            model_id,
            api_key=api_key,
            base_url=base_url,
            default_headers=headers or None,
            retry_policy=retry_policy,
            rng=rng,
        )


__all__ = [
    "OPENROUTER_API_KEY_ENV",
    "OPENROUTER_DEFAULT_BASE_URL",
    "OpenRouterProvider",
]
