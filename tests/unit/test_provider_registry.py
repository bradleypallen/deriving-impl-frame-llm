"""Tests for ``infereval.providers.get_provider`` registry dispatch."""

from __future__ import annotations

import pytest

from infereval.providers import ProviderConfigError, get_provider
from infereval.providers.mock import ScriptedProvider


class TestRegistry:
    def test_mock_provider(self) -> None:
        p = get_provider("mock", "any-model", responses=["GOOD"])
        assert isinstance(p, ScriptedProvider)

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ProviderConfigError, match="Unknown provider"):
            get_provider("nonexistent", "model-x")

    def test_name_is_case_insensitive(self) -> None:
        p = get_provider("MOCK", "any-model", responses=["X"])
        assert isinstance(p, ScriptedProvider)

    def test_name_is_whitespace_trimmed(self) -> None:
        p = get_provider("  mock  ", "any-model", responses=["X"])
        assert isinstance(p, ScriptedProvider)

    def test_passes_kwargs_through(self) -> None:
        p = get_provider("mock", "custom-id", responses=["A"], name="custom-mock")
        assert isinstance(p, ScriptedProvider)
        assert p.name == "custom-mock"
        assert p.model_id == "custom-id"
