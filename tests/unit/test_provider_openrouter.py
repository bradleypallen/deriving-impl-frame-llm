"""Tests for ``infereval.providers.openrouter.OpenRouterProvider``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from infereval.providers.base import ProviderConfigError
from infereval.providers.openrouter import (
    OPENROUTER_API_KEY_ENV,
    OPENROUTER_DEFAULT_BASE_URL,
    OpenRouterProvider,
)


class TestOpenRouterConfig:
    def test_missing_api_key_raises_config_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(OPENROUTER_API_KEY_ENV, raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)  # ensure no fallback
        with pytest.raises(ProviderConfigError, match="OPENROUTER_API_KEY"):
            OpenRouterProvider("anthropic/claude-3.5-sonnet")

    def test_uses_openrouter_env_var_not_openai(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(OPENROUTER_API_KEY_ENV, raising=False)
        # Even if OPENAI_API_KEY is set, OpenRouter should not pick it up
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        with pytest.raises(ProviderConfigError, match="OPENROUTER_API_KEY"):
            OpenRouterProvider("anthropic/claude-3.5-sonnet")

    def test_class_overrides_are_correct(self) -> None:
        assert OpenRouterProvider.name == "openrouter"
        assert OpenRouterProvider.DEFAULT_BASE_URL == OPENROUTER_DEFAULT_BASE_URL
        assert OpenRouterProvider.API_KEY_ENV == OPENROUTER_API_KEY_ENV


class TestOpenRouterClientConstruction:
    def test_default_base_url_passed_to_openai_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "sk-or-test")
        with patch("openai.OpenAI") as openai_class:
            OpenRouterProvider("anthropic/claude-3.5-sonnet")
            args, kwargs = openai_class.call_args
            assert kwargs["base_url"] == OPENROUTER_DEFAULT_BASE_URL
            assert kwargs["api_key"] == "sk-or-test"

    def test_attribution_headers_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "sk-or-test")
        with patch("openai.OpenAI") as openai_class:
            OpenRouterProvider(
                "anthropic/claude-3.5-sonnet",
                http_referer="https://example.com",
                x_title="infereval-test",
            )
            kwargs = openai_class.call_args.kwargs
            assert kwargs["default_headers"] == {
                "HTTP-Referer": "https://example.com",
                "X-Title": "infereval-test",
            }

    def test_no_headers_when_none_specified(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "sk-or-test")
        with patch("openai.OpenAI") as openai_class:
            OpenRouterProvider("anthropic/claude-3.5-sonnet")
            kwargs = openai_class.call_args.kwargs
            assert kwargs.get("default_headers") is None


class TestRegistry:
    """get_provider() dispatch."""

    def test_openrouter_via_registry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from infereval.providers import get_provider

        monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "sk-or-test")
        mock_client = MagicMock()
        with patch("openai.OpenAI", return_value=mock_client):
            p = get_provider("openrouter", "anthropic/claude-3.5-sonnet")
        assert isinstance(p, OpenRouterProvider)
        assert p.model_id == "anthropic/claude-3.5-sonnet"
