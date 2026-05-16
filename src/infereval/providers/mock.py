"""Mock providers for testing.

:class:`ScriptedProvider` returns a pre-determined sequence of responses,
cycling once the script is exhausted. Used in unit tests to verify the
endorsement pipeline against predetermined model behavior (majority vote,
tie-break, unparseable-as-abstain).

:class:`FailingProvider` always raises a chosen exception class; used to
test :class:`BaseProvider`'s retry classification.

:class:`ReplayProvider` replays a JSONL fixture of recorded provider
responses keyed by prompt hash. Use for deterministic end-to-end
regression tests that don't hit a real API.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..logging_setup import prompt_hash
from .base import (
    BaseProvider,
    ProviderConfigError,
    ProviderSampleError,
    RetryPolicy,
    SampleRequest,
    SampleResult,
)


@dataclass
class ScriptedProvider:
    """Returns a pre-determined sequence of responses, cycling on exhaustion.

    Each element may be either a plain ``str`` (in which case it is wrapped
    in a :class:`SampleResult` at sample time) or a fully-formed
    :class:`SampleResult`.

    Parameters
    ----------
    responses
        Sequence of responses to return on successive ``sample`` calls.
    model_id
        Identifier reported in :attr:`SampleResult.model_id`.
    name
        Identifier reported in :attr:`SampleResult.provider`. Defaults to
        ``"mock"`` so evaluation JSON written from a test cleanly identifies
        itself as not real.
    """

    responses: list[str | SampleResult]
    model_id: str = "scripted-mock-v1"
    name: str = "mock"
    _index: int = field(default=0, init=False, repr=False)

    def sample(self, req: SampleRequest) -> SampleResult:
        if not self.responses:
            raise ValueError("ScriptedProvider has no responses configured")
        i = self._index % len(self.responses)
        self._index += 1
        item = self.responses[i]
        if isinstance(item, SampleResult):
            # Caller specified the full SampleResult; preserve as-is but inject
            # request_id if we have one and they don't.
            if item.request_id is None and req.request_id is not None:
                return SampleResult(
                    text=item.text,
                    provider=item.provider,
                    model_id=item.model_id,
                    request_id=req.request_id,
                    wall_time_ms=item.wall_time_ms,
                    usage=item.usage,
                    raw=item.raw,
                )
            return item
        # plain string -> wrap as SampleResult
        return SampleResult(
            text=item,
            provider=self.name,
            model_id=self.model_id,
            request_id=req.request_id,
            wall_time_ms=0.0,
            usage={},
        )

    def reset(self) -> None:
        """Reset the index to the start of the response sequence."""
        self._index = 0


class FailingProvider(BaseProvider):
    """Provider that always raises a chosen exception class.

    Used in retry-loop tests to exercise the transient / non-transient
    classification. ``succeed_on_attempt`` (1-indexed) flips the provider
    to success once that attempt is reached; if ``None``, every attempt fails.
    """

    name = "failing-mock"

    def __init__(
        self,
        *,
        exc_factory: type[Exception] = RuntimeError,
        is_transient: bool = True,
        succeed_on_attempt: int | None = None,
        retry_policy: RetryPolicy | None = None,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(model_id="failing-mock-v1", retry_policy=retry_policy, rng=rng)
        self._exc_factory = exc_factory
        self._is_transient_flag = is_transient
        self._succeed_on = succeed_on_attempt
        self.attempts = 0
        self.sleeps: list[float] = []

    def _sample_once(self, req: SampleRequest) -> SampleResult:
        self.attempts += 1
        if self._succeed_on is not None and self.attempts >= self._succeed_on:
            return SampleResult(
                text="GOOD",
                provider=self.name,
                model_id=self.model_id,
                request_id=req.request_id,
                wall_time_ms=0.0,
                usage={},
            )
        raise self._exc_factory(f"simulated failure on attempt {self.attempts}")

    def _is_transient(self, exc: Exception) -> bool:
        return self._is_transient_flag

    def _sleep(self, seconds: float) -> None:
        # Record but do not actually sleep, so tests run instantly.
        self.sleeps.append(seconds)


@dataclass
class StaticOkProvider:
    """Trivial provider that always returns the same successful response.

    Used in tests that need a Provider but don't care about the response
    content (e.g. retry-recovery tests).
    """

    text: str = "GOOD"
    model_id: str = "static-ok-v1"
    name: str = "mock"

    def sample(self, req: SampleRequest) -> SampleResult:
        return SampleResult(
            text=self.text,
            provider=self.name,
            model_id=self.model_id,
            request_id=req.request_id,
            wall_time_ms=time.monotonic() * 1000.0,  # purely cosmetic
            usage={},
        )


class ReplayProvider:
    """Replays recorded provider responses from a JSONL fixture.

    The fixture is one JSON object per line. Each record must carry a
    ``prompt_hash`` (matching :func:`infereval.logging_setup.prompt_hash`
    of the prompt that produced it) and a ``text`` field. Optional fields:
    ``provider``, ``model_id``, ``request_id``, ``wall_time_ms``, ``usage``,
    ``raw``.

    When multiple records share a prompt hash, they are returned in
    fixture order; ``ReplayProvider`` cycles when the per-prompt sequence
    is exhausted, matching :class:`ScriptedProvider` semantics.

    Missing prompt hashes raise :class:`ProviderSampleError` with a
    diagnostic message listing how many hashes are recorded.

    This is the M8 vehicle for byte-for-byte regression testing of the
    endorsement pipeline without hitting a real API. Generate fixtures via
    the developer helper at ``tests/fixtures/build_stop_sign_replay.py``.
    """

    name = "replay"

    def __init__(
        self,
        fixture_path: Path | str,
        *,
        model_id: str | None = None,
    ) -> None:
        self.fixture_path = Path(fixture_path)
        if not self.fixture_path.exists():
            raise ProviderConfigError(
                f"ReplayProvider fixture not found: {self.fixture_path}"
            )

        records: dict[str, list[dict[str, Any]]] = {}
        with self.fixture_path.open("r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ProviderConfigError(
                        f"ReplayProvider fixture {self.fixture_path} line {line_no} "
                        f"is not valid JSON: {exc}"
                    ) from exc
                if "prompt_hash" not in record or "text" not in record:
                    raise ProviderConfigError(
                        f"ReplayProvider fixture {self.fixture_path} line {line_no} "
                        "missing required fields 'prompt_hash' and/or 'text'"
                    )
                records.setdefault(record["prompt_hash"], []).append(record)

        if not records:
            raise ProviderConfigError(
                f"ReplayProvider fixture {self.fixture_path} is empty"
            )

        self._records = records
        self._cursors: dict[str, int] = {}

        # Default model_id: explicit > first record's > generic placeholder.
        if model_id is not None:
            self.model_id = model_id
        else:
            first_record = next(iter(records.values()))[0]
            self.model_id = first_record.get("model_id", "replay-v1")

    def sample(self, req: SampleRequest) -> SampleResult:
        ph = prompt_hash(req.prompt)
        bucket = self._records.get(ph)
        if bucket is None:
            raise ProviderSampleError(
                f"ReplayProvider has no recorded response for prompt_hash={ph}. "
                f"Fixture {self.fixture_path} has {len(self._records)} hashes recorded; "
                "either the prompt template, the bearer expressions, or the "
                "context builder has changed since the fixture was generated. "
                "Regenerate the fixture or check the prompt."
            )
        idx = self._cursors.get(ph, 0) % len(bucket)
        self._cursors[ph] = idx + 1
        rec = bucket[idx]
        return SampleResult(
            text=rec["text"],
            provider=rec.get("provider", self.name),
            model_id=rec.get("model_id", self.model_id),
            request_id=req.request_id or rec.get("request_id"),
            wall_time_ms=float(rec.get("wall_time_ms", 0.0)),
            usage=dict(rec.get("usage") or {}),
            raw=rec.get("raw"),
        )

    def reset(self) -> None:
        """Reset all per-prompt cursors so replay restarts from the top."""
        self._cursors.clear()


__all__ = [
    "FailingProvider",
    "ReplayProvider",
    "ScriptedProvider",
    "StaticOkProvider",
]
