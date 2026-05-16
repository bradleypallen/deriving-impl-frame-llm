"""Tests for ``infereval.providers.anthropic.AnthropicProvider`` (SDK mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from infereval.providers.anthropic import ANTHROPIC_API_KEY_ENV, AnthropicProvider
from infereval.providers.base import ProviderConfigError, SampleRequest


def _fake_response(
    *,
    text: str = "GOOD",
    input_tokens: int = 7,
    output_tokens: int = 1,
    resp_id: str = "msg_test_123",
):
    """A SimpleNamespace mimicking the bits of an anthropic.types.Message we read."""
    return SimpleNamespace(
        id=resp_id,
        content=[SimpleNamespace(text=text, type="text")],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        model_dump=lambda: {"id": resp_id, "content": [{"text": text}]},
    )


def _provider_with_mock_client(create_returns) -> tuple[AnthropicProvider, MagicMock]:
    """Build an AnthropicProvider backed by a MagicMock client."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = create_returns
    return (
        AnthropicProvider("claude-opus-4-7", client=mock_client),
        mock_client,
    )


# ---- Configuration --------------------------------------------------------


class TestConfig:
    def test_missing_api_key_raises_config_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ANTHROPIC_API_KEY_ENV, raising=False)
        with pytest.raises(ProviderConfigError, match="ANTHROPIC_API_KEY"):
            AnthropicProvider("claude-opus-4-7")

    def test_explicit_api_key_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ANTHROPIC_API_KEY_ENV, raising=False)
        # Construct with explicit api_key; should not raise. We verify the client is built
        # by checking that the instance exists.
        p = AnthropicProvider("claude-opus-4-7", api_key="sk-ant-test")
        assert p.name == "anthropic"
        assert p.model_id == "claude-opus-4-7"

    def test_uses_env_when_no_explicit_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ANTHROPIC_API_KEY_ENV, "sk-ant-from-env")
        p = AnthropicProvider("claude-opus-4-7")
        assert p.name == "anthropic"

    def test_sdk_not_installed_raises_config_error(self) -> None:
        # Simulate the SDK being unavailable
        with (
            patch.dict("sys.modules", {"anthropic": None}),
            pytest.raises(ProviderConfigError, match="anthropic SDK not installed"),
        ):
            AnthropicProvider("claude-opus-4-7", api_key="sk-test")


# ---- Request construction -------------------------------------------------


class TestRequestConstruction:
    def test_minimal_request_shape(self) -> None:
        p, client = _provider_with_mock_client(_fake_response())
        p.sample(SampleRequest(prompt="Premises: X. Conclusion: Y. Verdict:"))
        client.messages.create.assert_called_once()
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["model"] == "claude-opus-4-7"
        assert kwargs["max_tokens"] == 32
        assert kwargs["temperature"] == 1.0
        assert kwargs["messages"] == [
            {"role": "user", "content": "Premises: X. Conclusion: Y. Verdict:"}
        ]
        # No system / stop / top_p in minimal request
        assert "system" not in kwargs
        assert "stop_sequences" not in kwargs
        assert "top_p" not in kwargs

    def test_system_message_passed_top_level(self) -> None:
        p, client = _provider_with_mock_client(_fake_response())
        p.sample(SampleRequest(prompt="Q", system="You are an evaluator."))
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["system"] == "You are an evaluator."

    def test_stop_sequences_translated(self) -> None:
        p, client = _provider_with_mock_client(_fake_response())
        p.sample(SampleRequest(prompt="Q", stop=("\n\n", "###")))
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["stop_sequences"] == ["\n\n", "###"]

    def test_top_p_forwarded(self) -> None:
        p, client = _provider_with_mock_client(_fake_response())
        p.sample(SampleRequest(prompt="Q", top_p=0.9))
        assert client.messages.create.call_args.kwargs["top_p"] == 0.9

    def test_seed_emits_warning_once(self, caplog: pytest.LogCaptureFixture) -> None:
        p, _ = _provider_with_mock_client(_fake_response())
        with caplog.at_level("WARNING", logger="infereval.providers.anthropic"):
            p.sample(SampleRequest(prompt="Q", seed=42))
            p.sample(SampleRequest(prompt="Q2", seed=42))
        warnings = [r for r in caplog.records if "seed_ignored" in r.getMessage()]
        assert len(warnings) == 1, "seed warning should be emitted at most once"

    def test_seed_not_passed_to_anthropic(self) -> None:
        p, client = _provider_with_mock_client(_fake_response())
        p.sample(SampleRequest(prompt="Q", seed=42))
        assert "seed" not in client.messages.create.call_args.kwargs


# ---- Response parsing -----------------------------------------------------


class TestResponseParsing:
    def test_text_extracted_from_blocks(self) -> None:
        p, _ = _provider_with_mock_client(_fake_response(text="BAD"))
        result = p.sample(SampleRequest(prompt="Q"))
        assert result.text == "BAD"
        assert result.provider == "anthropic"
        assert result.model_id == "claude-opus-4-7"

    def test_usage_recorded(self) -> None:
        p, _ = _provider_with_mock_client(_fake_response(input_tokens=42, output_tokens=3))
        result = p.sample(SampleRequest(prompt="Q"))
        assert result.usage == {"input_tokens": 42, "output_tokens": 3}

    def test_wall_time_recorded(self) -> None:
        p, _ = _provider_with_mock_client(_fake_response())
        result = p.sample(SampleRequest(prompt="Q"))
        assert result.wall_time_ms >= 0.0

    def test_request_id_from_response_when_not_set_on_req(self) -> None:
        p, _ = _provider_with_mock_client(_fake_response(resp_id="msg_aaa"))
        result = p.sample(SampleRequest(prompt="Q"))
        assert result.request_id == "msg_aaa"

    def test_req_request_id_overrides_response_id(self) -> None:
        p, _ = _provider_with_mock_client(_fake_response(resp_id="msg_bbb"))
        result = p.sample(SampleRequest(prompt="Q", request_id="client-correlation-id"))
        assert result.request_id == "client-correlation-id"

    def test_raw_payload_attached(self) -> None:
        p, _ = _provider_with_mock_client(_fake_response(text="GOOD"))
        result = p.sample(SampleRequest(prompt="Q"))
        assert result.raw is not None
        assert "id" in result.raw

    def test_multi_block_content_concatenated(self) -> None:
        resp = SimpleNamespace(
            id="msg_multi",
            content=[
                SimpleNamespace(text="GO", type="text"),
                SimpleNamespace(text="OD", type="text"),
            ],
            usage=SimpleNamespace(input_tokens=5, output_tokens=2),
            model_dump=lambda: {"id": "msg_multi"},
        )
        p, _ = _provider_with_mock_client(resp)
        result = p.sample(SampleRequest(prompt="Q"))
        assert result.text == "GOOD"


# ---- Transient classification ---------------------------------------------


class TestTransientClassification:
    def test_rate_limit_is_transient(self) -> None:
        import anthropic

        p = AnthropicProvider("claude-opus-4-7", api_key="sk-test")
        # Use the real class, no body required since _is_transient only does isinstance
        exc = anthropic.RateLimitError.__new__(anthropic.RateLimitError)
        assert p._is_transient(exc)

    def test_value_error_is_not_transient(self) -> None:
        p = AnthropicProvider("claude-opus-4-7", api_key="sk-test")
        assert not p._is_transient(ValueError("nope"))
