"""Tests for ``infereval.types``: Verdict, Bearer, Implication."""

from __future__ import annotations

import json

import pytest

from infereval.types import Bearer, Implication, Verdict

# ---- Verdict --------------------------------------------------------------


class TestVerdict:
    def test_string_values(self) -> None:
        assert Verdict.GOOD.value == "good"
        assert Verdict.BAD.value == "bad"
        assert Verdict.ABSTAIN.value == "abstain"

    def test_str_renders_as_value(self) -> None:
        assert str(Verdict.GOOD) == "good"
        assert f"{Verdict.ABSTAIN}" == "abstain"

    def test_json_serializes_as_value(self) -> None:
        # str-valued enum: json.dumps uses the string form
        assert json.dumps(Verdict.GOOD.value) == '"good"'

    def test_equality_with_string(self) -> None:
        # str-Enum mixin: Verdict.GOOD == "good"
        assert Verdict.GOOD == "good"

    def test_can_construct_from_string(self) -> None:
        assert Verdict("good") is Verdict.GOOD


# ---- Bearer ---------------------------------------------------------------


class TestBearer:
    def test_minimum_fields(self) -> None:
        b = Bearer(id="sa", expression="$a$ is a stop sign")
        assert b.id == "sa"
        assert b.expression == "$a$ is a stop sign"
        assert b.paraphrases == ()

    def test_hashable_and_equal(self) -> None:
        b1 = Bearer(id="sa", expression="x")
        b2 = Bearer(id="sa", expression="x")
        assert b1 == b2
        assert hash(b1) == hash(b2)

    def test_paraphrases_preserved(self) -> None:
        b = Bearer(id="sa", expression="x", paraphrases=("y", "z"))
        assert b.all_expressions() == ("x", "y", "z")

    def test_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        b = Bearer(id="sa", expression="x")
        with pytest.raises(FrozenInstanceError):
            b.expression = "y"  # type: ignore[misc]


# ---- Implication ----------------------------------------------------------


class TestImplication:
    def test_of_constructor(self) -> None:
        imp = Implication.of(["sa", "n"], ["ra"])
        assert imp.premises == frozenset({"sa", "n"})
        assert imp.conclusions == frozenset({"ra"})
        assert imp.id is None

    def test_equality_ignores_id(self) -> None:
        a = Implication.of(["sa"], ["ra"], id="row-0")
        b = Implication.of(["sa"], ["ra"], id="row-zero-alt")
        assert a == b
        assert hash(a) == hash(b)

    def test_set_semantics_for_premises(self) -> None:
        # Duplicates in input collapse: frozenset deduplicates
        a = Implication.of(["sa", "sa", "n"], ["ra"])
        b = Implication.of(["n", "sa"], ["ra"])
        assert a == b

    def test_distinct_when_premises_differ(self) -> None:
        a = Implication.of(["sa"], ["ra"])
        b = Implication.of(["sa", "ba"], ["ra"])
        assert a != b

    def test_usable_as_dict_key(self) -> None:
        d: dict[Implication, str] = {Implication.of(["sa"], ["ra"]): "x"}
        assert d[Implication.of(["sa"], ["ra"], id="any")] == "x"

    def test_is_empty_empty(self) -> None:
        assert Implication.of([], []).is_empty_empty
        assert not Implication.of(["sa"], []).is_empty_empty
        assert not Implication.of([], ["ra"]).is_empty_empty

    def test_intersects_clause_i(self) -> None:
        # Definition 3 clause (i): Gamma cap Delta != empty
        assert Implication.of(["sa"], ["sa", "ra"]).intersects()
        assert not Implication.of(["sa"], ["ra"]).intersects()
