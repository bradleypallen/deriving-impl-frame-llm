"""Tests for ``infereval.providers.base``: types, RetryPolicy, retry loop semantics."""

from __future__ import annotations

import random

import pytest

from infereval.providers.base import (
    BaseProvider,
    Provider,
    ProviderSampleError,
    RetryPolicy,
    SampleRequest,
    SampleResult,
)
from infereval.providers.mock import (
    FailingProvider,
    ScriptedProvider,
    StaticOkProvider,
)

# ---- Types -----------------------------------------------------------------


class TestTypes:
    def test_sample_request_defaults(self) -> None:
        r = SampleRequest(prompt="hi")
        assert r.prompt == "hi"
        assert r.system is None
        assert r.temperature == 1.0
        assert r.max_tokens == 1024
        assert r.top_p is None
        assert r.seed is None
        assert r.stop == ()
        assert r.request_id is None

    def test_sample_request_is_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        r = SampleRequest(prompt="hi")
        with pytest.raises(FrozenInstanceError):
            r.prompt = "bye"  # type: ignore[misc]

    def test_sample_result_minimal(self) -> None:
        r = SampleResult(text="GOOD", provider="mock", model_id="m1")
        assert r.usage == {}
        assert r.raw is None
        assert r.wall_time_ms == 0.0

    def test_scripted_provider_satisfies_protocol(self) -> None:
        p: Provider = ScriptedProvider(responses=["x"])
        assert isinstance(p, Provider)

    def test_static_ok_provider_satisfies_protocol(self) -> None:
        assert isinstance(StaticOkProvider(), Provider)


# ---- RetryPolicy -----------------------------------------------------------


class TestRetryPolicy:
    def test_defaults(self) -> None:
        p = RetryPolicy()
        assert p.max_attempts == 4
        assert p.backoff_initial_s == 0.5
        assert p.backoff_factor == 2.0
        assert p.jitter == 0.25

    def test_sleep_for_grows_exponentially_no_jitter(self) -> None:
        p = RetryPolicy(backoff_initial_s=1.0, backoff_factor=2.0, jitter=0.0)
        rng = random.Random(0)
        assert p.sleep_for(0, rng) == pytest.approx(1.0)
        assert p.sleep_for(1, rng) == pytest.approx(2.0)
        assert p.sleep_for(2, rng) == pytest.approx(4.0)
        assert p.sleep_for(3, rng) == pytest.approx(8.0)

    def test_sleep_for_with_jitter_in_range(self) -> None:
        p = RetryPolicy(backoff_initial_s=1.0, backoff_factor=2.0, jitter=0.25)
        rng = random.Random(0)
        # With 25% jitter, sleep is in [0.75 * base, 1.25 * base]
        for attempt in range(4):
            base = 1.0 * (2.0**attempt)
            s = p.sleep_for(attempt, rng)
            assert 0.75 * base <= s <= 1.25 * base

    def test_sleep_for_never_negative(self) -> None:
        # Pathological: jitter = 2.0 could push sleep negative, but it's clamped at 0
        p = RetryPolicy(backoff_initial_s=1.0, jitter=2.0)
        rng = random.Random(0)
        for attempt in range(10):
            assert p.sleep_for(attempt, rng) >= 0.0


# ---- Retry loop on BaseProvider --------------------------------------------


class TestBaseProviderRetry:
    def test_first_attempt_succeeds(self) -> None:
        p = FailingProvider(succeed_on_attempt=1)
        result = p.sample(SampleRequest(prompt="hi"))
        assert result.text == "GOOD"
        assert p.attempts == 1
        assert p.sleeps == []  # no retries needed

    def test_retries_then_succeeds(self) -> None:
        # Fails attempts 1 and 2, succeeds on attempt 3
        p = FailingProvider(
            is_transient=True,
            succeed_on_attempt=3,
            retry_policy=RetryPolicy(max_attempts=4, backoff_initial_s=0.1, jitter=0.0),
            rng=random.Random(0),
        )
        result = p.sample(SampleRequest(prompt="hi"))
        assert result.text == "GOOD"
        assert p.attempts == 3
        # Two sleeps between three attempts
        assert len(p.sleeps) == 2

    def test_exhausts_then_raises(self) -> None:
        p = FailingProvider(
            is_transient=True,
            succeed_on_attempt=None,  # never succeeds
            retry_policy=RetryPolicy(max_attempts=3, backoff_initial_s=0.01, jitter=0.0),
        )
        with pytest.raises(ProviderSampleError, match="after 3 attempts"):
            p.sample(SampleRequest(prompt="hi"))
        assert p.attempts == 3
        assert len(p.sleeps) == 2  # 2 sleeps between 3 attempts

    def test_non_transient_fails_fast(self) -> None:
        # Non-transient: first error aborts without retries
        p = FailingProvider(
            is_transient=False,
            succeed_on_attempt=None,
            retry_policy=RetryPolicy(max_attempts=5, backoff_initial_s=0.01, jitter=0.0),
        )
        with pytest.raises(ProviderSampleError, match="non-transient"):
            p.sample(SampleRequest(prompt="hi"))
        assert p.attempts == 1
        assert p.sleeps == []

    def test_max_attempts_one_means_no_retries(self) -> None:
        p = FailingProvider(
            is_transient=True,
            retry_policy=RetryPolicy(max_attempts=1, backoff_initial_s=0.01, jitter=0.0),
        )
        with pytest.raises(ProviderSampleError):
            p.sample(SampleRequest(prompt="hi"))
        assert p.attempts == 1
        assert p.sleeps == []


# ---- Custom subclass exercising the contract -------------------------------


class _NeverFailsProvider(BaseProvider):
    name = "never-fails"

    def __init__(self) -> None:
        super().__init__(model_id="x")
        self.calls = 0

    def _sample_once(self, req: SampleRequest) -> SampleResult:
        self.calls += 1
        return SampleResult(text="OK", provider=self.name, model_id=self.model_id)


class TestBaseProviderHappyPath:
    def test_single_call_no_retry(self) -> None:
        p = _NeverFailsProvider()
        result = p.sample(SampleRequest(prompt="hi"))
        assert result.text == "OK"
        assert p.calls == 1
