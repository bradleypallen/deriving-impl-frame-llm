"""Live provider smoke tests -- OPT-IN.

These tests hit real LLM APIs and cost real money. They are skipped unless
``RUN_LIVE_PROVIDER_TESTS=1`` is set in the environment.

Each test issues a single low-cost completion against the configured provider.
Assertions verify the round-trip mechanics (a non-error response with parseable
text and recorded usage) but do not assert specific verdicts -- model behavior
drifts over time.

Set the relevant API key in your environment:

- ``ANTHROPIC_API_KEY`` for the anthropic test
- ``OPENAI_API_KEY`` for the openai test
- ``OPENROUTER_API_KEY`` for the openrouter test
"""

from __future__ import annotations

import os

import pytest

from infereval.providers import SampleRequest, get_provider

LIVE = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PROVIDER_TESTS") != "1",
    reason="Set RUN_LIVE_PROVIDER_TESTS=1 to run live provider tests.",
)

PROMPT = (
    "Answer with one word, in uppercase, from {GOOD, BAD, ABSTAIN}. "
    "Question: Does 'the sky is blue' imply 'something is colored'? "
    "Verdict:"
)


@LIVE
@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
def test_anthropic_live_smoke() -> None:
    p = get_provider("anthropic", "claude-haiku-4-5-20251001")
    result = p.sample(SampleRequest(prompt=PROMPT, max_tokens=8, temperature=0.0))
    assert result.text  # something came back
    assert result.provider == "anthropic"
    assert result.wall_time_ms > 0.0


@LIVE
@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="no OPENAI_API_KEY")
def test_openai_live_smoke() -> None:
    p = get_provider("openai", "gpt-4o-mini")
    result = p.sample(SampleRequest(prompt=PROMPT, max_tokens=8, temperature=0.0))
    assert result.text
    assert result.provider == "openai"
    assert result.wall_time_ms > 0.0


@LIVE
@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("OPENROUTER_API_KEY"), reason="no OPENROUTER_API_KEY")
def test_openrouter_live_smoke() -> None:
    p = get_provider(
        "openrouter",
        "openai/gpt-4o-mini",
        http_referer="https://github.com/bradleypallen/infereval",
        x_title="infereval-test",
    )
    result = p.sample(SampleRequest(prompt=PROMPT, max_tokens=8, temperature=0.0))
    assert result.text
    assert result.provider == "openrouter"
    assert result.wall_time_ms > 0.0
