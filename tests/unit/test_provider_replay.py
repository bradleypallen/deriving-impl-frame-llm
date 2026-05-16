"""Tests for ``infereval.providers.mock.ReplayProvider``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from infereval.logging_setup import prompt_hash
from infereval.providers.base import (
    ProviderConfigError,
    ProviderSampleError,
    SampleRequest,
)
from infereval.providers.mock import ReplayProvider


def _write_fixture(tmp_path: Path, records: list[dict]) -> Path:
    """Write a list of records as JSONL, return the path."""
    path = tmp_path / "fixture.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


def _rec(prompt: str, text: str, **extra: object) -> dict:
    return {"prompt_hash": prompt_hash(prompt), "text": text, **extra}


# ---- Loading & validation -------------------------------------------------


class TestLoading:
    def test_missing_file_raises_config_error(self, tmp_path: Path) -> None:
        with pytest.raises(ProviderConfigError, match="not found"):
            ReplayProvider(tmp_path / "does-not-exist.jsonl")

    def test_empty_file_raises_config_error(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ProviderConfigError, match="empty"):
            ReplayProvider(path)

    def test_only_blank_lines_raises_config_error(self, tmp_path: Path) -> None:
        path = tmp_path / "blanks.jsonl"
        path.write_text("\n\n\n", encoding="utf-8")
        with pytest.raises(ProviderConfigError, match="empty"):
            ReplayProvider(path)

    def test_malformed_json_raises_config_error(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.jsonl"
        path.write_text("{not valid json\n", encoding="utf-8")
        with pytest.raises(ProviderConfigError, match="not valid JSON"):
            ReplayProvider(path)

    def test_missing_required_field_raises_config_error(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path, [{"text": "GOOD"}])  # no prompt_hash
        with pytest.raises(ProviderConfigError, match="missing required fields"):
            ReplayProvider(path)

    def test_blank_lines_are_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "mixed.jsonl"
        path.write_text(
            "\n"
            + json.dumps(_rec("p1", "GOOD"))
            + "\n\n"
            + json.dumps(_rec("p2", "BAD"))
            + "\n",
            encoding="utf-8",
        )
        rp = ReplayProvider(path)
        assert rp.sample(SampleRequest(prompt="p1")).text == "GOOD"
        assert rp.sample(SampleRequest(prompt="p2")).text == "BAD"


# ---- Lookup & cycling ----------------------------------------------------


class TestLookup:
    def test_returns_recorded_response(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path, [_rec("hello world", "GOOD")])
        rp = ReplayProvider(path)
        result = rp.sample(SampleRequest(prompt="hello world"))
        assert result.text == "GOOD"

    def test_propagates_provider_and_model_fields(self, tmp_path: Path) -> None:
        path = _write_fixture(
            tmp_path,
            [_rec("p", "GOOD", provider="anthropic", model_id="claude-x", wall_time_ms=42.5,
                  usage={"input_tokens": 5, "output_tokens": 1})],
        )
        rp = ReplayProvider(path)
        r = rp.sample(SampleRequest(prompt="p"))
        assert r.provider == "anthropic"
        assert r.model_id == "claude-x"
        assert r.wall_time_ms == 42.5
        assert r.usage == {"input_tokens": 5, "output_tokens": 1}

    def test_request_id_preferred_from_req_then_record(self, tmp_path: Path) -> None:
        path = _write_fixture(
            tmp_path, [_rec("p", "GOOD", request_id="recorded_rid")]
        )
        rp = ReplayProvider(path)
        # If request supplies an id, that wins
        r1 = rp.sample(SampleRequest(prompt="p", request_id="client_rid"))
        assert r1.request_id == "client_rid"
        # Otherwise fall back to the record's id
        rp.reset()
        r2 = rp.sample(SampleRequest(prompt="p"))
        assert r2.request_id == "recorded_rid"

    def test_default_model_id_from_first_record(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path, [_rec("p", "GOOD", model_id="claude-x")])
        rp = ReplayProvider(path)
        assert rp.model_id == "claude-x"

    def test_explicit_model_id_overrides_first_record(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path, [_rec("p", "GOOD", model_id="claude-x")])
        rp = ReplayProvider(path, model_id="my-override")
        assert rp.model_id == "my-override"

    def test_default_model_id_placeholder_when_record_lacks_it(
        self, tmp_path: Path
    ) -> None:
        path = _write_fixture(tmp_path, [_rec("p", "GOOD")])  # no model_id
        rp = ReplayProvider(path)
        assert rp.model_id == "replay-v1"


class TestCycling:
    def test_cycles_through_multiple_records_per_prompt(self, tmp_path: Path) -> None:
        path = _write_fixture(
            tmp_path,
            [
                _rec("p", "A"),
                _rec("p", "B"),
                _rec("p", "C"),
            ],
        )
        rp = ReplayProvider(path)
        req = SampleRequest(prompt="p")
        texts = [rp.sample(req).text for _ in range(7)]
        assert texts == ["A", "B", "C", "A", "B", "C", "A"]

    def test_independent_cursors_per_prompt(self, tmp_path: Path) -> None:
        path = _write_fixture(
            tmp_path,
            [
                _rec("p1", "1A"),
                _rec("p1", "1B"),
                _rec("p2", "2X"),
                _rec("p2", "2Y"),
            ],
        )
        rp = ReplayProvider(path)
        # Interleaved access; each prompt's cursor is independent
        assert rp.sample(SampleRequest(prompt="p1")).text == "1A"
        assert rp.sample(SampleRequest(prompt="p2")).text == "2X"
        assert rp.sample(SampleRequest(prompt="p1")).text == "1B"
        assert rp.sample(SampleRequest(prompt="p2")).text == "2Y"
        # After exhaustion, each cycles independently
        assert rp.sample(SampleRequest(prompt="p1")).text == "1A"
        assert rp.sample(SampleRequest(prompt="p2")).text == "2X"

    def test_reset_starts_from_beginning(self, tmp_path: Path) -> None:
        path = _write_fixture(
            tmp_path, [_rec("p", "A"), _rec("p", "B")]
        )
        rp = ReplayProvider(path)
        req = SampleRequest(prompt="p")
        rp.sample(req)
        rp.sample(req)
        rp.reset()
        assert rp.sample(req).text == "A"


# ---- Missing prompt -------------------------------------------------------


class TestMissingPrompt:
    def test_unknown_prompt_raises_sample_error(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path, [_rec("known prompt", "GOOD")])
        rp = ReplayProvider(path)
        with pytest.raises(ProviderSampleError, match="no recorded response"):
            rp.sample(SampleRequest(prompt="unknown prompt"))

    def test_error_message_lists_fixture_path(self, tmp_path: Path) -> None:
        path = _write_fixture(tmp_path, [_rec("p1", "GOOD"), _rec("p2", "BAD")])
        rp = ReplayProvider(path)
        with pytest.raises(ProviderSampleError) as exc_info:
            rp.sample(SampleRequest(prompt="missing"))
        msg = str(exc_info.value)
        assert "2 hashes recorded" in msg
        assert str(path) in msg
