"""Tests for ``infereval.benchmark``: Pydantic validation + JSON round-trip."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from infereval.benchmark import Benchmark, BenchmarkItem
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
