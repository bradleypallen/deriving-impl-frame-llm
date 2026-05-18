"""Anthropic Claude provider.

Wraps :class:`anthropic.Anthropic` and its Messages API. The ``anthropic``
SDK is an optional dependency: ``pip install 'infereval[anthropic]'``.

Anthropic's API does not honor a ``seed`` parameter. If a seed is supplied
in :class:`SampleRequest`, we log a one-time warning and proceed; the seed
is recorded in the evaluation file as supplied so analysts can see what was
intended, even though the model did not act on it.
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
    import anthropic

log = logging.getLogger(__name__)

ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"


def _rejects_temperature(model_id: str) -> bool:
    """Detect Claude models that reject the ``temperature`` parameter outright.

    As of 2026-05, ``claude-opus-4-7`` (and later Opus versions, presumably)
    deprecate ``temperature`` and return a 400 if it is supplied. Sonnet
    and Haiku still accept it.
    """
    if not model_id:
        return False
    bare = model_id.split("/", 1)[-1].lower()
    # claude-opus-4-7, claude-opus-4-8, etc.
    if bare.startswith(("claude-opus-4-7", "claude-opus-4.7")):
        return True
    # Generation-agnostic: claude-opus-5+ likely keeps the same posture.
    return any(bare.startswith(f"claude-opus-{n}") for n in range(5, 10))


class AnthropicProvider(BaseProvider):
    """Anthropic Claude backend (Messages API)."""

    name = "anthropic"

    def __init__(
        self,
        model_id: str,
        *,
        api_key: str | None = None,
        client: anthropic.Anthropic | None = None,
        retry_policy: RetryPolicy | None = None,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(model_id, retry_policy=retry_policy, rng=rng)
        self._client = client if client is not None else self._build_client(api_key)
        self._seed_warning_emitted = False

    @staticmethod
    def _build_client(api_key: str | None) -> anthropic.Anthropic:
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderConfigError(
                "anthropic SDK not installed. Install with: pip install 'infereval[anthropic]'"
            ) from exc
        key = api_key if api_key is not None else os.environ.get(ANTHROPIC_API_KEY_ENV)
        if not key:
            raise ProviderConfigError(
                f"{ANTHROPIC_API_KEY_ENV} not set and no api_key provided"
            )
        return anthropic.Anthropic(api_key=key)

    def _sample_once(self, req: SampleRequest) -> SampleResult:
        if req.seed is not None and not self._seed_warning_emitted:
            log.warning(
                "provider.anthropic.seed_ignored",
                extra={
                    "model_id": self.model_id,
                    "reason": (
                        "Anthropic API does not honor 'seed'; recording the "
                        "requested value but the model did not use it"
                    ),
                },
            )
            self._seed_warning_emitted = True

        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": req.max_tokens,
            "messages": [{"role": "user", "content": req.prompt}],
        }
        # Claude Opus 4.7+ has deprecated the ``temperature`` parameter and
        # rejects requests that include it. Skip it for those models;
        # everything else still accepts it.
        if not _rejects_temperature(self.model_id):
            kwargs["temperature"] = req.temperature
        if req.top_p is not None:
            kwargs["top_p"] = req.top_p
        if req.system:
            kwargs["system"] = req.system
        if req.stop:
            kwargs["stop_sequences"] = list(req.stop)

        start = time.monotonic()
        response = self._client.messages.create(**kwargs)
        wall_time_ms = (time.monotonic() - start) * 1000.0

        text_parts: list[str] = []
        for block in getattr(response, "content", []) or []:
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str):
                text_parts.append(block_text)
        text = "".join(text_parts)

        usage_obj = getattr(response, "usage", None)
        usage: dict[str, int] = {}
        if usage_obj is not None:
            in_tok = getattr(usage_obj, "input_tokens", None)
            out_tok = getattr(usage_obj, "output_tokens", None)
            if isinstance(in_tok, int):
                usage["input_tokens"] = in_tok
            if isinstance(out_tok, int):
                usage["output_tokens"] = out_tok

        raw: dict[str, Any] | None = None
        if hasattr(response, "model_dump"):
            try:
                raw = response.model_dump()
            except Exception:  # noqa: BLE001 -- raw is best-effort, never fatal
                raw = None

        provider_request_id = getattr(response, "id", None)
        request_id = req.request_id if req.request_id is not None else provider_request_id

        log_event(
            log,
            "provider.anthropic.sample",
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
            import anthropic
        except ImportError:
            return False
        transient_types: tuple[type[Exception], ...] = (
            anthropic.RateLimitError,
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.InternalServerError,
        )
        return isinstance(exc, transient_types)


__all__ = ["ANTHROPIC_API_KEY_ENV", "AnthropicProvider"]
