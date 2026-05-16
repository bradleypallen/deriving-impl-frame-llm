"""Tests for ``infereval.providers.mock.ScriptedProvider``."""

from __future__ import annotations

import pytest

from infereval.providers.base import SampleRequest, SampleResult
from infereval.providers.mock import ScriptedProvider


class TestScriptedProvider:
    def test_returns_responses_in_order(self) -> None:
        p = ScriptedProvider(responses=["A", "B", "C"])
        req = SampleRequest(prompt="?")
        assert p.sample(req).text == "A"
        assert p.sample(req).text == "B"
        assert p.sample(req).text == "C"

    def test_cycles_after_exhaustion(self) -> None:
        p = ScriptedProvider(responses=["A", "B"])
        req = SampleRequest(prompt="?")
        assert [p.sample(req).text for _ in range(5)] == ["A", "B", "A", "B", "A"]

    def test_empty_responses_raises(self) -> None:
        p = ScriptedProvider(responses=[])
        with pytest.raises(ValueError, match="no responses"):
            p.sample(SampleRequest(prompt="?"))

    def test_propagates_request_id(self) -> None:
        p = ScriptedProvider(responses=["A"])
        result = p.sample(SampleRequest(prompt="?", request_id="run-1:item-2:sample-0"))
        assert result.request_id == "run-1:item-2:sample-0"
        assert result.provider == "mock"
        assert result.model_id == "scripted-mock-v1"

    def test_can_return_full_sample_result(self) -> None:
        canned = SampleResult(
            text="X",
            provider="recorded",
            model_id="recorded-v1",
            request_id="abc",
            wall_time_ms=99.0,
            usage={"input_tokens": 10, "output_tokens": 1},
        )
        p = ScriptedProvider(responses=[canned])
        result = p.sample(SampleRequest(prompt="?", request_id="should-be-preserved"))
        # The canned result had its own request_id; preserve it.
        assert result.request_id == "abc"
        assert result.usage == {"input_tokens": 10, "output_tokens": 1}

    def test_sample_result_with_no_request_id_inherits_from_req(self) -> None:
        canned = SampleResult(text="X", provider="r", model_id="v", request_id=None)
        p = ScriptedProvider(responses=[canned])
        result = p.sample(SampleRequest(prompt="?", request_id="from-req"))
        assert result.request_id == "from-req"

    def test_reset_starts_from_beginning(self) -> None:
        p = ScriptedProvider(responses=["A", "B"])
        req = SampleRequest(prompt="?")
        p.sample(req)
        p.sample(req)
        p.reset()
        assert p.sample(req).text == "A"
