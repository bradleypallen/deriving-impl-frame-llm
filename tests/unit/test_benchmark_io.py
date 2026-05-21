"""Tests for ``infereval.benchmark``: Pydantic validation + JSON round-trip."""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from infereval.benchmark import (
    BearerModel,
    Benchmark,
    BenchmarkItem,
    ConstructionMetadata,
    FactorConstraints,
    Reference,
)
from infereval.types import Verdict

# ---- Pydantic validation -------------------------------------------------


class TestValidation:
    def test_loads_valid_stop_sign(self, stop_sign_benchmark_dict: dict) -> None:
        bench = Benchmark.model_validate(stop_sign_benchmark_dict)
        assert bench.id == "stop-sign-example-1"
        assert bench.m == 1
        assert bench.n == 4

    def test_rejects_unknown_bearer_in_premise(self, stop_sign_benchmark_dict: dict) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["items"][0]["premises"].append("ghost-bearer")
        with pytest.raises(ValidationError, match="unknown bearer ids"):
            Benchmark.model_validate(d)

    def test_rejects_unknown_bearer_in_conclusion(
        self, stop_sign_benchmark_dict: dict
    ) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["items"][0]["conclusions"] = ["definitely-not-a-bearer"]
        with pytest.raises(ValidationError, match="unknown bearer ids"):
            Benchmark.model_validate(d)

    def test_rejects_unknown_bearer_in_rsr_target(
        self, stop_sign_benchmark_dict: dict
    ) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["items"][0]["rsr_target"] = {"X": ["sa", "missing"], "A": ["ra"]}
        with pytest.raises(ValidationError, match="rsr_target references unknown"):
            Benchmark.model_validate(d)

    def test_rejects_duplicate_item_id(self, stop_sign_benchmark_dict: dict) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["items"][1]["id"] = d["items"][0]["id"]
        with pytest.raises(ValidationError, match="Duplicate item id"):
            Benchmark.model_validate(d)

    def test_rejects_duplicate_analyst_id(self, stop_sign_benchmark_dict: dict) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["analysts"].append({"id": d["analysts"][0]["id"]})
        # m would still be 2 but ids duplicate; verdict tuple would mismatch too
        d["items"][0]["analyst_verdicts"] = ["good", "good"]
        d["items"][1]["analyst_verdicts"] = ["good", "good"]
        d["items"][2]["analyst_verdicts"] = ["good", "good"]
        d["items"][3]["analyst_verdicts"] = ["bad", "bad"]
        with pytest.raises(ValidationError, match="Analyst ids must be unique"):
            Benchmark.model_validate(d)

    def test_rejects_mismatched_analyst_verdict_length(
        self, stop_sign_benchmark_dict: dict
    ) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["items"][0]["analyst_verdicts"] = ["good", "good"]  # m=1 but 2 verdicts
        with pytest.raises(ValidationError, match="analyst verdicts"):
            Benchmark.model_validate(d)

    def test_requires_at_least_one_analyst(self, stop_sign_benchmark_dict: dict) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["analysts"] = []
        with pytest.raises(ValidationError):
            Benchmark.model_validate(d)

    def test_rejects_extra_top_level_fields(self, stop_sign_benchmark_dict: dict) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["random_extra_field"] = "unexpected"
        with pytest.raises(ValidationError):
            Benchmark.model_validate(d)


# ---- Normalization & set semantics --------------------------------------


class TestNormalization:
    def test_premises_dedup_and_sort(self) -> None:
        item = BenchmarkItem(
            id="x",
            premises=["b", "a", "a"],  # dup + unsorted
            conclusions=["c"],
            analyst_verdicts=[Verdict.GOOD],
        )
        assert item.premises == ["a", "b"]

    def test_conclusions_dedup_and_sort(self) -> None:
        item = BenchmarkItem(
            id="x",
            premises=["a"],
            conclusions=["z", "m", "z"],
            analyst_verdicts=[Verdict.GOOD],
        )
        assert item.conclusions == ["m", "z"]

    def test_to_implication_uses_frozenset(self) -> None:
        item = BenchmarkItem(
            id="row-2",
            premises=["sa", "nr", "n"],
            conclusions=["ra"],
            analyst_verdicts=[Verdict.GOOD],
        )
        imp = item.to_implication()
        assert imp.premises == frozenset({"sa", "n", "nr"})
        assert imp.conclusions == frozenset({"ra"})
        assert imp.id == "row-2"


# ---- JSON round-trip ----------------------------------------------------


class TestJsonRoundtrip:
    def test_dumps_then_loads_equal(self, stop_sign_benchmark_dict: dict) -> None:
        bench = Benchmark.model_validate(stop_sign_benchmark_dict)
        text = bench.dumps()
        round_tripped = Benchmark.loads(text)
        assert round_tripped == bench

    def test_dump_and_load_from_disk(
        self, stop_sign_benchmark_dict: dict, tmp_path: Path
    ) -> None:
        bench = Benchmark.model_validate(stop_sign_benchmark_dict)
        path = tmp_path / "stop_sign.json"
        bench.dump(path)
        loaded = Benchmark.load(path)
        assert loaded == bench

    def test_dump_emits_sorted_premise_lists(
        self, stop_sign_benchmark_dict: dict
    ) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["items"][2]["premises"] = ["n", "sa", "nr"]  # un-sorted on input
        bench = Benchmark.model_validate(d)
        text = bench.dumps()
        data = json.loads(text)
        row2 = next(it for it in data["items"] if it["id"] == "row-2")
        assert row2["premises"] == sorted(row2["premises"])

    def test_runtime_bearers_constructed_correctly(
        self, stop_sign_benchmark: Benchmark
    ) -> None:
        bearers = stop_sign_benchmark.runtime_bearers()
        assert bearers["sa"].id == "sa"
        assert bearers["sa"].expression == "$a$ is a stop sign"
        assert bearers["sa"].paraphrases == ()

    def test_analyst_index_lookup(self, stop_sign_benchmark: Benchmark) -> None:
        assert stop_sign_benchmark.analyst_index("paper-author") == 0
        with pytest.raises(KeyError):
            stop_sign_benchmark.analyst_index("nobody")


# ---- Context-builder discriminated union --------------------------------


class TestContextBuilders:
    def test_default_premise_uses_and_joiner(
        self, stop_sign_benchmark: Benchmark
    ) -> None:
        cb = stop_sign_benchmark.context_builders.premise
        assert cb.kind == "template"
        assert cb.joiner == " and "

    def test_default_conclusion_uses_or_joiner(
        self, stop_sign_benchmark: Benchmark
    ) -> None:
        cb = stop_sign_benchmark.context_builders.conclusion
        assert cb.kind == "template"
        assert cb.joiner == " or "

    def test_can_override_to_plugin(self, stop_sign_benchmark_dict: dict) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["context_builders"] = {
            "premise": {"kind": "plugin", "plugin": "my_pkg.builders:premise_fn"},
            "conclusion": {"kind": "template", "template": "{expressions}", "joiner": " or "},
        }
        bench = Benchmark.model_validate(d)
        assert bench.context_builders.premise.kind == "plugin"
        assert bench.context_builders.premise.plugin == "my_pkg.builders:premise_fn"


# ---- Verification-prompt override ---------------------------------------


class TestVerificationPromptOverride:
    """The benchmark JSON can fully specify a custom verification prompt
    (system + user template + parse regex + id) without dropping to Python."""

    def test_template_only(self, stop_sign_benchmark_dict: dict) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["verification_prompt"] = {"template": "{premise_context} ?> {conclusion_context}"}
        bench = Benchmark.model_validate(d)
        assert bench.verification_prompt is not None
        assert bench.verification_prompt.template.startswith("{premise_context}")
        assert bench.verification_prompt.system is None  # defaults to None → DEFAULT
        assert bench.verification_prompt.id is None

    def test_full_override_in_json(self, stop_sign_benchmark_dict: dict) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["verification_prompt"] = {
            "template": "P: {premise_context}\nC: {conclusion_context}\nVerdict:",
            "system": "You are evaluating defeasible material inference.",
            "parse_regex": r"\b(GOOD|BAD|ABSTAIN)\b",
            "id": "my-defeasible-v1",
        }
        bench = Benchmark.model_validate(d)
        vp = bench.verification_prompt
        assert vp is not None
        assert vp.system == "You are evaluating defeasible material inference."
        assert vp.id == "my-defeasible-v1"
        assert vp.parse_regex == r"\b(GOOD|BAD|ABSTAIN)\b"

    def test_resolve_uses_override_system_when_supplied(
        self, stop_sign_benchmark_dict: dict
    ) -> None:
        from infereval.prompts import resolve_verification_prompt

        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["verification_prompt"] = {
            "template": "{premise_context}|{conclusion_context}",
            "system": "Custom system message here.",
            "id": "custom-v7",
        }
        bench = Benchmark.model_validate(d)
        prompt = resolve_verification_prompt(bench.verification_prompt)
        assert prompt.system == "Custom system message here."
        assert prompt.id == "custom-v7"
        assert prompt.user_template == "{premise_context}|{conclusion_context}"

    def test_unknown_fields_rejected(self, stop_sign_benchmark_dict: dict) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["verification_prompt"] = {
            "template": "{premise_context}/{conclusion_context}",
            "garbage_field": "nope",
        }
        with pytest.raises(ValidationError):
            Benchmark.model_validate(d)


# ---- References ----------------------------------------------------------


class TestReferences:
    """``Reference`` model + per-level ``references`` field (Issue #18)."""

    def test_reference_minimal_only_citation(self) -> None:
        # Only ``citation`` is required; the rest may be omitted.
        r = Reference(citation="Berlin def, JAMA 2012")
        assert r.citation == "Berlin def, JAMA 2012"
        assert r.doi is None and r.url is None and r.section is None and r.note is None

    def test_reference_full_payload(self) -> None:
        r = Reference(
            citation="Maisel et al. (2002). N Engl J Med 347(3), 161-167.",
            doi="10.1056/NEJMoa020233",
            url="https://www.nejm.org/doi/full/10.1056/NEJMoa020233",
            section="Table 2",
            note="BNP cutoffs and NPV for HF",
        )
        dumped = r.model_dump(exclude_none=True)
        assert dumped["doi"] == "10.1056/NEJMoa020233"
        assert dumped["section"] == "Table 2"
        assert dumped["note"] == "BNP cutoffs and NPV for HF"

    def test_reference_rejects_unknown_fields(self) -> None:
        # ``extra="forbid"`` — typos in field names should fail loudly.
        with pytest.raises(ValidationError):
            Reference.model_validate({"citation": "ok", "auther": "typo"})

    def test_string_shorthand_promoted_on_item(self) -> None:
        # A plain string in the list auto-promotes to Reference(citation=s).
        item = BenchmarkItem(
            id="t",
            premises=["a"],
            conclusions=["b"],
            analyst_verdicts=["good"],
            references=[
                "Just a string",
                {"citation": "Structured", "doi": "10.1/foo"},
            ],
        )
        assert len(item.references) == 2
        assert isinstance(item.references[0], Reference)
        assert item.references[0].citation == "Just a string"
        assert item.references[0].doi is None
        assert item.references[1].citation == "Structured"
        assert item.references[1].doi == "10.1/foo"

    def test_string_shorthand_promoted_on_bearer(self) -> None:
        b = BearerModel(expression="X", references=["Source A", "Source B"])
        assert [r.citation for r in b.references] == ["Source A", "Source B"]

    def test_references_default_empty_on_all_three_levels(
        self, stop_sign_benchmark_dict: dict
    ) -> None:
        # Backwards-compatibility: an existing benchmark JSON with no
        # ``references`` fields anywhere still validates, and the field
        # defaults to ``[]`` on Benchmark, every BearerModel, and every
        # BenchmarkItem.
        bench = Benchmark.model_validate(stop_sign_benchmark_dict)
        assert bench.references == []
        assert all(b.references == [] for b in bench.bearers.values())
        assert all(it.references == [] for it in bench.items)

    def test_references_populated_at_all_three_levels(
        self, stop_sign_benchmark_dict: dict
    ) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["references"] = [
            {
                "citation": "Simonelli (2026). The Stop Sign Dialogue.",
                "doi": "10.1234/dialogue",
            }
        ]
        first_bearer_key = next(iter(d["bearers"]))
        d["bearers"][first_bearer_key]["references"] = ["Carving rationale, p. 3"]
        d["items"][0]["references"] = [
            "Allen (2026). Note on Simonelli's Stop Sign Dialogue.",
            {"citation": "Hlobil & Brandom (2025)", "section": "Definition 3"},
        ]
        bench = Benchmark.model_validate(d)
        assert bench.references[0].doi == "10.1234/dialogue"
        assert bench.bearers[first_bearer_key].references[0].citation == "Carving rationale, p. 3"
        assert len(bench.items[0].references) == 2
        assert bench.items[0].references[1].section == "Definition 3"

    def test_references_round_trip_through_dumps(
        self, stop_sign_benchmark_dict: dict
    ) -> None:
        d = copy.deepcopy(stop_sign_benchmark_dict)
        d["items"][0]["references"] = [
            {"citation": "X et al.", "doi": "10.1/x", "section": "Sec 1"},
        ]
        bench = Benchmark.model_validate(d)
        reloaded = Benchmark.loads(bench.dumps())
        # Round-trip preserves the structured fields.
        assert reloaded.items[0].references[0].citation == "X et al."
        assert reloaded.items[0].references[0].doi == "10.1/x"
        assert reloaded.items[0].references[0].section == "Sec 1"
        # exclude_none drops the unset fields from the JSON output.
        json_text = bench.dumps()
        assert "url" not in json_text
        assert "note" not in json_text

    def test_reference_in_item_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError):
            BenchmarkItem(
                id="t",
                premises=["a"],
                conclusions=["b"],
                analyst_verdicts=["good"],
                references=[{"citation": "ok", "made_up": True}],
            )


# ---- Factorial design (Issue #30, Phase 1.1) ----------------------------


def _minimal_factorial_dict(
    factors: dict[str, list[str]] | None = None,
    items_factor_levels: list[dict[str, str]] | None = None,
    factor_constraints: dict | None = None,
) -> dict:
    """Build a minimal valid benchmark dict with the supplied factorial design.

    The base benchmark has 2 bearers, 1 analyst, and one item per entry
    in ``items_factor_levels`` (each item gets a synthetic id ``i0`` … ``iN``).
    """
    items_factor_levels = items_factor_levels or []
    factors = factors or {}
    d: dict = {
        "schema_version": "1.0",
        "id": "factorial-test",
        "bearers": {"p": {"expression": "P"}, "q": {"expression": "Q"}},
        "analysts": [{"id": "a"}],
        "items": [
            {
                "id": f"i{i}",
                "premises": ["p"],
                "conclusions": ["q"],
                "analyst_verdicts": ["good"],
                "factor_levels": fl,
            }
            for i, fl in enumerate(items_factor_levels)
        ],
    }
    if factors:
        d["factors"] = factors
    if factor_constraints is not None:
        d["factor_constraints"] = factor_constraints
    return d


class TestFactorialDesign:
    """``factors`` / ``factor_levels`` / ``factor_constraints`` (Phase 1.1)."""

    def test_existing_benchmark_loads_without_factors(self, stop_sign_benchmark_dict: dict) -> None:
        # Backwards-compat regression: an unannotated benchmark validates
        # cleanly with empty factors and empty factor_levels everywhere.
        bench = Benchmark.model_validate(stop_sign_benchmark_dict)
        assert bench.factors == {}
        assert bench.factor_constraints is None
        for item in bench.items:
            assert item.factor_levels == {}

    def test_well_formed_factorial_design_validates(self) -> None:
        d = _minimal_factorial_dict(
            factors={"premise_type": ["base", "supporter"], "para": ["v1", "v2"]},
            items_factor_levels=[
                {"premise_type": "base", "para": "v1"},
                {"premise_type": "base", "para": "v2"},
                {"premise_type": "supporter", "para": "v1"},
                {"premise_type": "supporter", "para": "v2"},
            ],
        )
        bench = Benchmark.model_validate(d)
        assert bench.factors == {"premise_type": ["base", "supporter"], "para": ["v1", "v2"]}
        assert len(bench.items[0].factor_levels) == 2

    def test_rejects_unknown_factor_key(self) -> None:
        d = _minimal_factorial_dict(
            factors={"premise_type": ["base", "supporter"]},
            items_factor_levels=[{"premise_type": "base"}, {"bogus_factor": "x"}],
        )
        with pytest.raises(ValidationError, match="not declared at the benchmark level"):
            Benchmark.model_validate(d)

    def test_rejects_unknown_level_value(self) -> None:
        d = _minimal_factorial_dict(
            factors={"premise_type": ["base", "supporter"]},
            items_factor_levels=[
                {"premise_type": "base"},
                {"premise_type": "ghost-level"},
            ],
        )
        with pytest.raises(ValidationError, match="not a declared level for"):
            Benchmark.model_validate(d)

    def test_cells_counts_items_per_crossed_cell(self) -> None:
        d = _minimal_factorial_dict(
            factors={"pt": ["a", "b"], "para": ["v1", "v2"]},
            items_factor_levels=[
                {"pt": "a", "para": "v1"},
                {"pt": "a", "para": "v1"},  # 2 items in (a, v1)
                {"pt": "a", "para": "v2"},
                {"pt": "b", "para": "v1"},
                # cell (b, v2) is empty on purpose
            ],
        )
        bench = Benchmark.model_validate(d)
        cells = bench.cells()
        # Cell-keys ordered by sorted factor names: (para, pt)
        assert cells[("v1", "a")] == 2
        assert cells[("v2", "a")] == 1
        assert cells[("v1", "b")] == 1
        assert cells[("v2", "b")] == 0
        assert sum(cells.values()) == 4

    def test_is_fully_crossed_at_k(self) -> None:
        d = _minimal_factorial_dict(
            factors={"pt": ["a", "b"]},
            items_factor_levels=[{"pt": "a"}, {"pt": "a"}, {"pt": "b"}, {"pt": "b"}],
        )
        bench = Benchmark.model_validate(d)
        assert bench.is_fully_crossed_at_k(1)
        assert bench.is_fully_crossed_at_k(2)
        assert not bench.is_fully_crossed_at_k(3)

    def test_is_fully_crossed_returns_false_when_no_factors(
        self, stop_sign_benchmark_dict: dict
    ) -> None:
        bench = Benchmark.model_validate(stop_sign_benchmark_dict)
        # No factors declared -> trivially fails any factorial check.
        assert not bench.is_fully_crossed_at_k(1)

    def test_min_items_per_cell_accepts_well_populated_design(self) -> None:
        d = _minimal_factorial_dict(
            factors={"pt": ["a", "b"]},
            items_factor_levels=[
                {"pt": "a"}, {"pt": "a"}, {"pt": "b"}, {"pt": "b"},
            ],
            factor_constraints={"min_items_per_cell": 2},
        )
        bench = Benchmark.model_validate(d)
        assert bench.factor_constraints is not None
        assert bench.factor_constraints.min_items_per_cell == 2

    def test_min_items_per_cell_rejects_underpopulation(self) -> None:
        d = _minimal_factorial_dict(
            factors={"pt": ["a", "b"]},
            items_factor_levels=[{"pt": "a"}, {"pt": "b"}],  # 1 item per cell
            factor_constraints={"min_items_per_cell": 3},
        )
        with pytest.raises(ValidationError, match="min_items_per_cell=3 not met"):
            Benchmark.model_validate(d)

    def test_min_items_per_cell_with_none_skips_the_floor_check(self) -> None:
        # FactorConstraints(min_items_per_cell=None) should not raise even
        # if cells are empty — author explicitly opted out of the floor.
        d = _minimal_factorial_dict(
            factors={"pt": ["a", "b"]},
            items_factor_levels=[{"pt": "a"}],  # cell (b,) is empty
            factor_constraints={"min_items_per_cell": None},
        )
        bench = Benchmark.model_validate(d)
        assert bench.cells()[("a",)] == 1
        assert bench.cells()[("b",)] == 0

    def test_factor_constraints_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError):
            FactorConstraints.model_validate({"min_items_per_cell": 1, "garbage": True})

    def test_items_without_factor_levels_dont_contaminate_cells(self) -> None:
        # An item that doesn't carry factor_levels for every declared
        # factor belongs to no cell and is excluded from cells() counts.
        d = _minimal_factorial_dict(
            factors={"pt": ["a", "b"]},
            items_factor_levels=[{"pt": "a"}, {}],  # second item has no factor_levels
        )
        bench = Benchmark.model_validate(d)
        cells = bench.cells()
        assert cells[("a",)] == 1
        assert cells[("b",)] == 0
        # Total counted = 1 (the item with no factor_levels is excluded)
        assert sum(cells.values()) == 1


# ---- Paraphrase variants helper (Issue #32, Phase 1.2) ------------------


class TestParaphraseVariantsHelper:
    """``Benchmark.n_paraphrase_variants`` reflects the runtime variant count."""

    def test_returns_one_when_no_paraphrases(self, stop_sign_benchmark_dict: dict) -> None:
        # Stop-sign bearers have no paraphrases.
        bench = Benchmark.model_validate(stop_sign_benchmark_dict)
        assert bench.n_paraphrase_variants == 1

    def test_returns_one_plus_max_paraphrase_count(self) -> None:
        data = {
            "schema_version": "1.0",
            "id": "para-helper",
            "bearers": {
                "sa": {"expression": "a is a stop sign",
                       "paraphrases": ["alt1", "alt2", "alt3"]},
                "ra": {"expression": "a is red", "paraphrases": ["alt1"]},
                "n": {"expression": "it is nighttime"},  # no paraphrases
            },
            "analysts": [{"id": "a"}],
            "items": [{
                "id": "i1", "premises": ["sa"], "conclusions": ["ra"],
                "analyst_verdicts": ["good"],
            }],
        }
        bench = Benchmark.model_validate(data)
        # max paraphrases = 3 (on sa); variant count = 4.
        assert bench.n_paraphrase_variants == 4


# ---- Construction provenance (Issue #34, Phase 1.3) ---------------------


class TestConstructionMetadata:
    """``BenchmarkItem.construction_metadata`` carries per-item provenance."""

    def test_well_formed_metadata_validates(self) -> None:
        cm = ConstructionMetadata(
            authored_by="physician-c",
            authored_on=date(2026, 4, 15),
            authored_blind_to_models=["claude-opus-4-7", "gpt-5"],
            source="Sanford Guide 2025",
        )
        assert cm.authored_by == "physician-c"
        assert cm.authored_on == date(2026, 4, 15)
        assert cm.authored_blind_to_models == ["claude-opus-4-7", "gpt-5"]
        assert cm.source == "Sanford Guide 2025"

    def test_all_fields_optional(self) -> None:
        # Empty payload is fine — every field has a default.
        cm = ConstructionMetadata()
        assert cm.authored_by is None
        assert cm.authored_on is None
        assert cm.authored_blind_to_models == []
        assert cm.source is None

    def test_authored_on_parses_iso_string(self) -> None:
        cm = ConstructionMetadata.model_validate({"authored_on": "2026-04-15"})
        assert cm.authored_on == date(2026, 4, 15)

    def test_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            ConstructionMetadata.model_validate({"authored_by": "x", "garbage": True})

    def test_item_carries_metadata_through_load(self) -> None:
        data = {
            "schema_version": "1.0",
            "id": "cm-load",
            "bearers": {"p": {"expression": "P"}, "q": {"expression": "Q"}},
            "analysts": [{"id": "a"}],
            "items": [
                {
                    "id": "i1",
                    "premises": ["p"],
                    "conclusions": ["q"],
                    "analyst_verdicts": ["good"],
                    "construction_metadata": {
                        "authored_by": "physician-c",
                        "authored_on": "2026-04-15",
                        "authored_blind_to_models": ["claude-opus-4-7"],
                        "source": "Sanford Guide 2025",
                    },
                }
            ],
        }
        bench = Benchmark.model_validate(data)
        cm = bench.items[0].construction_metadata
        assert cm is not None
        assert cm.authored_by == "physician-c"
        assert cm.authored_on == date(2026, 4, 15)
        assert cm.authored_blind_to_models == ["claude-opus-4-7"]

    def test_default_is_none(self, stop_sign_benchmark_dict: dict) -> None:
        bench = Benchmark.model_validate(stop_sign_benchmark_dict)
        for item in bench.items:
            assert item.construction_metadata is None

    def test_round_trip_preserves_metadata(self) -> None:
        data = {
            "schema_version": "1.0",
            "id": "cm-rt",
            "bearers": {"p": {"expression": "P"}, "q": {"expression": "Q"}},
            "analysts": [{"id": "a"}],
            "items": [
                {
                    "id": "i1",
                    "premises": ["p"],
                    "conclusions": ["q"],
                    "analyst_verdicts": ["good"],
                    "construction_metadata": {
                        "authored_by": "x",
                        "authored_on": "2026-04-15",
                    },
                }
            ],
        }
        bench = Benchmark.model_validate(data)
        reloaded = Benchmark.loads(bench.dumps())
        cm = reloaded.items[0].construction_metadata
        assert cm is not None
        assert cm.authored_by == "x"
        assert cm.authored_on == date(2026, 4, 15)
        # Unset fields are excluded from output (exclude_none) but parse back to None.
        assert cm.source is None
        assert cm.authored_blind_to_models == []


# ---- Reference panels (Issue #36, Phase 1.4) ----------------------------


def _panelled_benchmark_dict() -> dict:
    return {
        "schema_version": "1.0",
        "id": "panel-test",
        "bearers": {"p": {"expression": "P"}, "q": {"expression": "Q"}},
        "analysts": [
            {"id": "a1", "panel": "primary"},
            {"id": "a2", "panel": "primary"},
            {"id": "a3", "panel": "reviewer"},
        ],
        "primary_panel": "primary",
        "items": [
            {"id": "i1", "premises": ["p"], "conclusions": ["q"],
             "analyst_verdicts": ["good", "good", "good"]},
        ],
    }


class TestReferencePanels:
    """``AnalystModel.panel`` + ``Benchmark.primary_panel`` + helpers."""

    def test_well_formed_panelled_benchmark_validates(self) -> None:
        bench = Benchmark.model_validate(_panelled_benchmark_dict())
        assert bench.panel_names() == ["primary", "reviewer"]

    def test_partial_panel_rejected(self) -> None:
        d = _panelled_benchmark_dict()
        # Remove panel from the middle analyst -> partial.
        d["analysts"][1].pop("panel")
        with pytest.raises(ValidationError, match="Partial-panel"):
            Benchmark.model_validate(d)

    def test_primary_panel_must_exist(self) -> None:
        d = _panelled_benchmark_dict()
        d["primary_panel"] = "ghost"
        with pytest.raises(ValidationError, match="primary_panel='ghost'"):
            Benchmark.model_validate(d)

    def test_analyst_indices_in_panel(self) -> None:
        bench = Benchmark.model_validate(_panelled_benchmark_dict())
        assert bench.analyst_indices_in_panel("primary") == [0, 1]
        assert bench.analyst_indices_in_panel("reviewer") == [2]
        assert bench.analyst_indices_in_panel("nonexistent") == []

    def test_resolved_primary_panel(self) -> None:
        # Explicit primary_panel wins.
        bench = Benchmark.model_validate(_panelled_benchmark_dict())
        assert bench.resolved_primary_panel() == "primary"

        # Unset primary_panel falls back to alphabetically-first panel name.
        d = _panelled_benchmark_dict()
        d["primary_panel"] = None
        bench2 = Benchmark.model_validate(d)
        assert bench2.resolved_primary_panel() == "primary"

    def test_unpanelled_benchmark_unchanged(self, stop_sign_benchmark_dict: dict) -> None:
        bench = Benchmark.model_validate(stop_sign_benchmark_dict)
        assert bench.panel_names() == []
        assert bench.primary_panel is None
        assert bench.resolved_primary_panel() is None


# ---- factor_kinds (v0.5.3, review fix #4) -------------------------------


class TestFactorKinds:
    """``factor_kinds`` valence labels on declared factors."""

    def test_well_formed_factor_kinds_validate(self) -> None:
        d = _minimal_factorial_dict(
            factors={"role": ["base", "supporter"], "para": ["v1", "v2"]},
            items_factor_levels=[
                {"role": "base", "para": "v1"},
                {"role": "supporter", "para": "v2"},
            ],
        )
        d["factor_kinds"] = {"role": "substantive", "para": "experimentally_controlled"}
        bench = Benchmark.model_validate(d)
        assert bench.factor_kinds == {
            "role": "substantive",
            "para": "experimentally_controlled",
        }

    def test_default_is_empty_dict(self) -> None:
        d = _minimal_factorial_dict(
            factors={"role": ["base", "supporter"]},
            items_factor_levels=[{"role": "base"}, {"role": "supporter"}],
        )
        bench = Benchmark.model_validate(d)
        assert bench.factor_kinds == {}

    def test_unknown_factor_in_factor_kinds_rejected(self) -> None:
        d = _minimal_factorial_dict(
            factors={"role": ["base", "supporter"]},
            items_factor_levels=[{"role": "base"}, {"role": "supporter"}],
        )
        d["factor_kinds"] = {"phantom": "substantive"}
        with pytest.raises(ValidationError, match="references unknown factor"):
            Benchmark.model_validate(d)

    def test_invalid_kind_value_rejected_by_literal(self) -> None:
        d = _minimal_factorial_dict(
            factors={"role": ["base", "supporter"]},
            items_factor_levels=[{"role": "base"}, {"role": "supporter"}],
        )
        d["factor_kinds"] = {"role": "ambiguous"}  # not in the Literal
        with pytest.raises(ValidationError):
            Benchmark.model_validate(d)

    def test_partial_factor_kinds_coverage_is_allowed(self) -> None:
        """Not every declared factor needs a valence label; unlabelled
        factors get the historical neutral negative-finding summary.
        """
        d = _minimal_factorial_dict(
            factors={"role": ["base", "supporter"], "para": ["v1", "v2"]},
            items_factor_levels=[
                {"role": "base", "para": "v1"},
                {"role": "supporter", "para": "v2"},
            ],
        )
        d["factor_kinds"] = {"role": "substantive"}  # para omitted
        bench = Benchmark.model_validate(d)
        assert bench.factor_kinds == {"role": "substantive"}


# ---- Analyst rationales (v0.5.4, AR1–AR12) -------------------------------


def _rationale_bench_dict(
    *,
    analysts: list[dict] | None = None,
    items: list[dict] | None = None,
) -> dict:
    """Minimal valid benchmark for the rationale tests."""
    return {
        "schema_version": "1.0",
        "id": "rationale-test",
        "bearers": {"p": {"expression": "P"}, "q": {"expression": "Q"}},
        "analysts": analysts or [{"id": "a"}, {"id": "b"}],
        "items": items or [],
    }


class TestAnalystRationales:
    """AR1–AR12: per-analyst, per-item rationale field."""

    # AR3 — backward compatibility: rationale-free benchmarks load unchanged.
    def test_absent_field_loads_as_none(self) -> None:
        d = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "good"]},
            ],
        )
        bench = Benchmark.model_validate(d)
        assert bench.items[0].analyst_rationales is None

    def test_stop_sign_loads_with_no_rationales(self, stop_sign_benchmark_dict: dict) -> None:
        """The committed stop-sign benchmark must validate unchanged
        (it carries no analyst_rationales field at all)."""
        bench = Benchmark.model_validate(stop_sign_benchmark_dict)
        for item in bench.items:
            assert item.analyst_rationales is None

    # AR2 — additive: verdicts are still bare enum values.
    def test_verdicts_stay_bare_enum_values(self) -> None:
        d = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"],
                 "analyst_rationales": ["because P", "because not P"]},
            ],
        )
        bench = Benchmark.model_validate(d)
        # Verdicts remain Verdict enum members, untouched by rationales.
        from infereval.types import Verdict as V
        assert bench.items[0].analyst_verdicts == [V.GOOD, V.BAD]
        assert bench.items[0].analyst_rationales == ["because P", "because not P"]

    # AR4 — empty-string vs. None distinction.
    def test_empty_string_entry_distinct_from_none(self) -> None:
        d = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"],
                 "analyst_rationales": ["explained", ""]},
            ],
        )
        bench = Benchmark.model_validate(d)
        # Field is present (a list), one entry is the empty string.
        assert bench.items[0].analyst_rationales == ["explained", ""]
        # And None on a sibling item means something else entirely.
        d2 = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"]},
            ],
        )
        bench2 = Benchmark.model_validate(d2)
        assert bench2.items[0].analyst_rationales is None

    # AR5 — length consistency.
    def test_too_few_rationales_rejected(self) -> None:
        d = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"],
                 "analyst_rationales": ["only one"]},
            ],
        )
        with pytest.raises(ValidationError, match=r"i1.*1 analyst rationales.*2 analysts"):
            Benchmark.model_validate(d)

    def test_too_many_rationales_rejected(self) -> None:
        d = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"],
                 "analyst_rationales": ["a", "b", "c"]},
            ],
        )
        with pytest.raises(ValidationError, match=r"i1.*3 analyst rationales.*2 analysts"):
            Benchmark.model_validate(d)

    def test_correct_length_passes(self) -> None:
        d = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"],
                 "analyst_rationales": ["x", "y"]},
            ],
        )
        bench = Benchmark.model_validate(d)
        assert len(bench.items[0].analyst_rationales) == 2

    # AR6 — no content enforcement (empty + whitespace + None entries allowed).
    def test_content_not_enforced(self) -> None:
        """The framework validates structure and length only. Empty
        strings and whitespace are fine — content quality is the
        analyst's responsibility, not a schema-enforceable one."""
        d = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"],
                 "analyst_rationales": ["", "   "]},
            ],
        )
        bench = Benchmark.model_validate(d)
        assert bench.items[0].analyst_rationales == ["", "   "]

    # AR7 — extra="forbid" compatibility: it's a declared field, not a
    # smuggling slot. Misspellings get rejected.
    def test_misspelled_field_rejected(self) -> None:
        d = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"],
                 "analyst_rational": ["x", "y"]},  # typo
            ],
        )
        with pytest.raises(ValidationError, match="Extra inputs"):
            Benchmark.model_validate(d)

    # AR12 — round-trip preservation through dump/load.
    def test_round_trip_preserves_present_list(self) -> None:
        d_in = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"],
                 "analyst_rationales": ["because P", ""]},
            ],
        )
        bench = Benchmark.model_validate(d_in)
        d_out = bench.model_dump(mode="json", exclude_none=True)
        bench2 = Benchmark.model_validate(d_out)
        assert bench2.items[0].analyst_rationales == ["because P", ""]

    def test_round_trip_preserves_none(self) -> None:
        d_in = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"]},
            ],
        )
        bench = Benchmark.model_validate(d_in)
        # exclude_none drops the field on dump — that's correct.
        d_out = bench.model_dump(mode="json", exclude_none=True)
        assert "analyst_rationales" not in d_out["items"][0]
        bench2 = Benchmark.model_validate(d_out)
        assert bench2.items[0].analyst_rationales is None

    def test_round_trip_preserves_empty_strings_distinct_from_none(self) -> None:
        """The contrast that matters: a list of empty strings is *not*
        the same as a missing field."""
        d_with = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"],
                 "analyst_rationales": ["", ""]},
            ],
        )
        d_without = _rationale_bench_dict(
            items=[
                {"id": "i1", "premises": ["p"], "conclusions": ["q"],
                 "analyst_verdicts": ["good", "bad"]},
            ],
        )
        b_with = Benchmark.model_validate(d_with)
        b_without = Benchmark.model_validate(d_without)
        assert b_with.items[0].analyst_rationales == ["", ""]
        assert b_without.items[0].analyst_rationales is None
        # And after round-trip the distinction is preserved.
        b_with_round = Benchmark.model_validate(
            b_with.model_dump(mode="json", exclude_none=True)
        )
        b_without_round = Benchmark.model_validate(
            b_without.model_dump(mode="json", exclude_none=True)
        )
        assert b_with_round.items[0].analyst_rationales == ["", ""]
        assert b_without_round.items[0].analyst_rationales is None
