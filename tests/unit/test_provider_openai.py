"""Tests for ``infereval.providers.openai.OpenAIProvider`` (SDK mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from infereval.providers.base import ProviderConfigError, SampleRequest
from infereval.providers.openai import OPENAI_API_KEY_ENV, OpenAIProvider


def _fake_response(
    *,
    text: str = "GOOD",
    prompt_tokens: int = 10,
    completion_tokens: int = 1,
    resp_id: str = "chatcmpl_test_123",
):
    return SimpleNamespace(
        id=resp_id,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text, role="assistant"),
                index=0,
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
        model_dump=lambda: {"id": resp_id, "choices": [{"message": {"content": text}}]},
    )


def _provider_with_mock_client(create_returns) -> tuple[OpenAIProvider, MagicMock]:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = create_returns
    return (
        OpenAIProvider("gpt-4o", client=mock_client),
        mock_client,
    )


# ---- Configuration --------------------------------------------------------


class TestConfig:
    def test_missing_api_key_raises_config_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
        with pytest.raises(ProviderConfigError, match="OPENAI_API_KEY"):
            OpenAIProvider("gpt-4o")

    def test_explicit_api_key_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
        p = OpenAIProvider("gpt-4o", api_key="sk-test")
        assert p.name == "openai"
        assert p.model_id == "gpt-4o"

    def test_sdk_not_installed_raises(self) -> None:
        with (
            patch.dict("sys.modules", {"openai": None}),
            pytest.raises(ProviderConfigError, match="openai SDK not installed"),
        ):
            OpenAIProvider("gpt-4o", api_key="sk-test")


# ---- Request construction -------------------------------------------------


class TestRequestConstruction:
    def test_user_message_only_when_no_system(self) -> None:
        p, client = _provider_with_mock_client(_fake_response())
        p.sample(SampleRequest(prompt="Q?"))
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "gpt-4o"
        assert kwargs["messages"] == [{"role": "user", "content": "Q?"}]
        assert kwargs["max_tokens"] == 32
        assert kwargs["temperature"] == 1.0

    def test_system_message_prepended(self) -> None:
        p, client = _provider_with_mock_client(_fake_response())
        p.sample(SampleRequest(prompt="Q?", system="You are an evaluator."))
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["messages"] == [
            {"role": "system", "content": "You are an evaluator."},
            {"role": "user", "content": "Q?"},
        ]

    def test_seed_forwarded(self) -> None:
        p, client = _provider_with_mock_client(_fake_response())
        p.sample(SampleRequest(prompt="Q", seed=42))
        assert client.chat.completions.create.call_args.kwargs["seed"] == 42

    def test_stop_forwarded(self) -> None:
        p, client = _provider_with_mock_client(_fake_response())
        p.sample(SampleRequest(prompt="Q", stop=("###",)))
        assert client.chat.completions.create.call_args.kwargs["stop"] == ["###"]

    def test_top_p_forwarded(self) -> None:
        p, client = _provider_with_mock_client(_fake_response())
        p.sample(SampleRequest(prompt="Q", top_p=0.9))
        assert client.chat.completions.create.call_args.kwargs["top_p"] == 0.9

    def test_gpt5_uses_max_completion_tokens(self) -> None:
        # gpt-5.x and the o-series reject 'max_tokens' as unsupported.
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_response()
        p = OpenAIProvider("gpt-5.4", client=mock_client)
        p.sample(SampleRequest(prompt="Q", max_tokens=512))
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["max_completion_tokens"] == 512
        assert "max_tokens" not in kwargs

    def test_o4_mini_uses_max_completion_tokens(self) -> None:
        # The o-series reasoning models behave the same way.
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_response()
        p = OpenAIProvider("o4-mini", client=mock_client)
        p.sample(SampleRequest(prompt="Q", max_tokens=128))
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["max_completion_tokens"] == 128
        assert "max_tokens" not in kwargs

    def test_gpt4o_uses_legacy_max_tokens(self) -> None:
        # Pre-5.x non-reasoning models still expect 'max_tokens'.
        p, client = _provider_with_mock_client(_fake_response())  # uses gpt-4o
        p.sample(SampleRequest(prompt="Q", max_tokens=32))
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["max_tokens"] == 32
        assert "max_completion_tokens" not in kwargs


# ---- Response parsing -----------------------------------------------------


class TestResponseParsing:
    def test_text_extracted(self) -> None:
        p, _ = _provider_with_mock_client(_fake_response(text="ABSTAIN"))
        r = p.sample(SampleRequest(prompt="Q"))
        assert r.text == "ABSTAIN"
        assert r.provider == "openai"
        assert r.model_id == "gpt-4o"

    def test_usage_recorded(self) -> None:
        p, _ = _provider_with_mock_client(_fake_response(prompt_tokens=100, completion_tokens=5))
        r = p.sample(SampleRequest(prompt="Q"))
        assert r.usage == {"input_tokens": 100, "output_tokens": 5}

    def test_request_id_propagation(self) -> None:
        p, _ = _provider_with_mock_client(_fake_response(resp_id="chatcmpl_abc"))
        r1 = p.sample(SampleRequest(prompt="Q"))
        assert r1.request_id == "chatcmpl_abc"

        r2 = p.sample(SampleRequest(prompt="Q", request_id="client-id"))
        assert r2.request_id == "client-id"

    def test_empty_content_yields_empty_text(self) -> None:
        resp = SimpleNamespace(
            id="x",
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=None),
                    index=0,
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=0),
            model_dump=lambda: {},
        )
        p, _ = _provider_with_mock_client(resp)
        r = p.sample(SampleRequest(prompt="Q"))
        assert r.text == ""


# ---- Transient classification ---------------------------------------------


class TestTransientClassification:
    def test_rate_limit_is_transient(self) -> None:
        import openai

        p = OpenAIProvider("gpt-4o", api_key="sk-test")
        exc = openai.RateLimitError.__new__(openai.RateLimitError)
        assert p._is_transient(exc)

    def test_value_error_is_not_transient(self) -> None:
        p = OpenAIProvider("gpt-4o", api_key="sk-test")
        assert not p._is_transient(ValueError("nope"))
