"""OpenAI provider (Chat Completions API).

Wraps :class:`openai.OpenAI` against the Chat Completions endpoint. Chat
Completions is chosen over the newer Responses API for breadth of model
coverage across OpenRouter — :class:`infereval.providers.openrouter.OpenRouterProvider`
inherits from this class with only a base-URL swap.

The ``openai`` SDK is an optional dependency: ``pip install 'infereval[openai]'``.
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import TYPE_CHECKING, Any

from infereval.logging_setup import log_event

from .base import (
    BaseProvider,
    ProviderConfigError,
    RetryPolicy,
    SampleRequest,
    SampleResult,
)

if TYPE_CHECKING:
    import openai as _openai_sdk

log = logging.getLogger(__name__)

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(BaseProvider):
    """OpenAI Chat Completions backend.

    Subclasses may override the class attributes :attr:`name`,
    :attr:`DEFAULT_BASE_URL`, and :attr:`API_KEY_ENV` to target
    OpenAI-API-compatible services (see :class:`OpenRouterProvider`).
    """

    name = "openai"
    DEFAULT_BASE_URL = OPENAI_DEFAULT_BASE_URL
    API_KEY_ENV = OPENAI_API_KEY_ENV

    def __init__(
        self,
        model_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
        client: _openai_sdk.OpenAI | None = None,
        retry_policy: RetryPolicy | None = None,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(model_id, retry_policy=retry_policy, rng=rng)
        self._client = (
            client
            if client is not None
            else self._build_client(api_key, base_url, default_headers)
        )

    @classmethod
    def _build_client(
        cls,
        api_key: str | None,
        base_url: str | None,
        default_headers: dict[str, str] | None,
    ) -> _openai_sdk.OpenAI:
        try:
            import openai
        except ImportError as exc:
            raise ProviderConfigError(
                "openai SDK not installed. Install with: pip install 'infereval[openai]'"
            ) from exc
        key = api_key if api_key is not None else os.environ.get(cls.API_KEY_ENV)
        if not key:
            raise ProviderConfigError(
                f"{cls.API_KEY_ENV} not set and no api_key provided"
            )
        return openai.OpenAI(
            api_key=key,
            base_url=base_url if base_url is not None else cls.DEFAULT_BASE_URL,
            default_headers=default_headers or None,
        )

    def _sample_once(self, req: SampleRequest) -> SampleResult:
        messages: list[dict[str, str]] = []
        if req.system:
            messages.append({"role": "system", "content": req.system})
        messages.append({"role": "user", "content": req.prompt})

        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
        }
        if req.top_p is not None:
            kwargs["top_p"] = req.top_p
        if req.seed is not None:
            kwargs["seed"] = req.seed
        if req.stop:
            kwargs["stop"] = list(req.stop)

        start = time.monotonic()
        response = self._client.chat.completions.create(**kwargs)
        wall_time_ms = (time.monotonic() - start) * 1000.0

        text = ""
        choices = getattr(response, "choices", None) or []
        if choices:
            msg = getattr(choices[0], "message", None)
            text = (getattr(msg, "content", None) or "") if msg is not None else ""

        usage_obj = getattr(response, "usage", None)
        usage: dict[str, int] = {}
        if usage_obj is not None:
            in_tok = getattr(usage_obj, "prompt_tokens", None)
            out_tok = getattr(usage_obj, "completion_tokens", None)
            if isinstance(in_tok, int):
                usage["input_tokens"] = in_tok
            if isinstance(out_tok, int):
                usage["output_tokens"] = out_tok

        raw: dict[str, Any] | None = None
        if hasattr(response, "model_dump"):
            try:
                raw = response.model_dump()
            except Exception:  # noqa: BLE001
                raw = None

        provider_request_id = getattr(response, "id", None)
        request_id = req.request_id if req.request_id is not None else provider_request_id

        log_event(
            log,
            f"provider.{self.name}.sample",
            model_id=self.model_id,
            request_id=request_id,
            wall_time_ms=wall_time_ms,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )

        return SampleResult(
            text=text,
            provider=self.name,
            model_id=self.model_id,
            request_id=request_id,
            wall_time_ms=wall_time_ms,
            usage=usage,
            raw=raw,
        )

    def _is_transient(self, exc: Exception) -> bool:
        try:
            import openai
        except ImportError:
            return False
        transient_types: tuple[type[Exception], ...] = (
            openai.RateLimitError,
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.InternalServerError,
        )
        return isinstance(exc, transient_types)


__all__ = ["OPENAI_API_KEY_ENV", "OPENAI_DEFAULT_BASE_URL", "OpenAIProvider"]
