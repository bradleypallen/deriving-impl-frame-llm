"""Tests for ``infereval.benchmark``: Pydantic validation + JSON round-trip."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from infereval.benchmark import BearerModel, Benchmark, BenchmarkItem, Reference
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
