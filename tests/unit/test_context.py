"""Tests for ``infereval.context``: strip_tex_math, template/plugin builders."""

from __future__ import annotations

import pytest

from infereval.benchmark import PluginContextBuilder, TemplateContextBuilder
from infereval.context import (
    PluginResolutionError,
    make_template_builder,
    resolve_context_builder,
    resolve_context_builders,
    resolve_plugin,
    strip_tex_math,
)

# ---- strip_tex_math --------------------------------------------------------


class TestStripTexMath:
    def test_single_delimiter_pair_removed(self) -> None:
        assert strip_tex_math("$a$ is a stop sign") == "a is a stop sign"

    def test_multiple_delimiter_pairs_removed(self) -> None:
        assert strip_tex_math("$a$ and $b$ are red") == "a and b are red"

    def test_no_delimiters_passes_through(self) -> None:
        assert strip_tex_math("it is nighttime") == "it is nighttime"

    def test_lone_dollar_preserved(self) -> None:
        # An unmatched $ has no closing pair; we leave it alone.
        assert strip_tex_math("price is $5") == "price is $5"

    def test_empty_string(self) -> None:
        assert strip_tex_math("") == ""

    def test_only_delimiters(self) -> None:
        assert strip_tex_math("$x$") == "x"

    def test_stop_sign_all_paper_bearers(self) -> None:
        # The five bearers from Example 1 of the paper
        cases = [
            ("$a$ is a stop sign", "a is a stop sign"),
            ("$a$ is red", "a is red"),
            ("it is nighttime", "it is nighttime"),
            ("$a$ is not made with reflective material", "a is not made with reflective material"),
            ("$a$ has been painted blue", "a has been painted blue"),
        ]
        for src, expected in cases:
            assert strip_tex_math(src) == expected


# ---- make_template_builder -------------------------------------------------


class TestTemplateBuilder:
    def test_default_joiner_and(self) -> None:
        b = make_template_builder(joiner=" and ")
        assert b(["a is red", "b is blue"]) == "a is red and b is blue"

    def test_default_joiner_or(self) -> None:
        b = make_template_builder(joiner=" or ")
        assert b(["x", "y"]) == "x or y"

    def test_single_expression(self) -> None:
        b = make_template_builder(joiner=" and ")
        assert b(["only this"]) == "only this"

    def test_template_wraps_output(self) -> None:
        b = make_template_builder(template="It is the case that {expressions}.", joiner=" and ")
        assert b(["x", "y"]) == "It is the case that x and y."

    def test_empty_input_returns_template_with_empty_expressions(self) -> None:
        b = make_template_builder(template="{expressions}", joiner=" and ")
        assert b([]) == ""


# ---- Plugin builder --------------------------------------------------------


# Defined at module scope so importlib can resolve it.
def _example_premise_builder(expressions):  # type: ignore[no-untyped-def]
    return "PREMISES: " + " | ".join(expressions)


class TestResolvePlugin:
    def test_colon_separator(self) -> None:
        fn = resolve_plugin("tests.unit.test_context:_example_premise_builder")
        assert fn(["x", "y"]) == "PREMISES: x | y"

    def test_dot_separator(self) -> None:
        fn = resolve_plugin("tests.unit.test_context._example_premise_builder")
        assert fn(["x"]) == "PREMISES: x"

    def test_unknown_module_raises(self) -> None:
        with pytest.raises(PluginResolutionError, match="Could not import"):
            resolve_plugin("no.such.module:fn")

    def test_unknown_attribute_raises(self) -> None:
        with pytest.raises(PluginResolutionError, match="has no attribute"):
            resolve_plugin("tests.unit.test_context:no_such_function")

    def test_non_callable_raises(self) -> None:
        # `strip_tex_math` is callable; let's reference something that isn't.
        # Use a module attribute that is a string.
        with pytest.raises(PluginResolutionError, match="not callable"):
            resolve_plugin("tests.unit.test_context:_NOT_CALLABLE")

    def test_invalid_path_no_separator_raises(self) -> None:
        with pytest.raises(PluginResolutionError, match="not a valid dotted path"):
            resolve_plugin("bareword")


_NOT_CALLABLE = "I am a string, not a function"


# ---- resolve_context_builder ----------------------------------------------


class TestResolveContextBuilder:
    def test_template_model(self) -> None:
        m = TemplateContextBuilder(template="{expressions}", joiner=" and ")
        b = resolve_context_builder(m)
        assert b(["a", "b"]) == "a and b"

    def test_plugin_model(self) -> None:
        m = PluginContextBuilder(plugin="tests.unit.test_context:_example_premise_builder")
        b = resolve_context_builder(m)
        assert b(["x", "y"]) == "PREMISES: x | y"

    def test_pair_resolution_from_benchmark(self, stop_sign_benchmark) -> None:
        prem, conc = resolve_context_builders(stop_sign_benchmark.context_builders)
        assert prem(["a is a stop sign", "it is nighttime"]) == \
            "a is a stop sign and it is nighttime"
        assert conc(["a is red"]) == "a is red"
