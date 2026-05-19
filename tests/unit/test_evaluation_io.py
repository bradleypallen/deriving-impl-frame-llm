"""Tests for ``infereval.evaluation``: Pydantic validation + JSON round-trip + endorsements view."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from infereval.evaluation import (
    EndorsementConfig,
    Evaluation,
    EvaluationItem,
    MajorityVote,
    ModelInfo,
    ProviderParams,
    SampleRecord,
)
from infereval.frame import DerivedFrame
from infereval.types import Implication, Verdict


def _minimal_eval_dict(verdicts_by_row: dict[str, str]) -> dict:
    """Build a minimal stop-sign evaluation dict mirroring Example 1."""
    rows = [
        ("row-0", ["sa"], ["ra"], ["good"]),
        ("row-1", ["n", "sa"], ["ra"], ["good"]),
        ("row-2", ["n", "nr", "sa"], ["ra"], ["good"]),
        ("row-3", ["ba", "sa"], ["ra"], ["bad"]),
    ]
    return {
        "schema_version": "1.0",
        "id": "run-0001",
        "benchmark_id": "stop-sign-example-1",
        "model": {
            "provider": "mock",
            "model_id": "test-model-v1",
            "params": {"temperature": 1.0, "max_tokens": 32},
        },
        "items": [
            {
                "id": rid,
                "premises": prem,
                "conclusions": conc,
                "analyst_verdicts": av,
                "model_verdict": verdicts_by_row[rid],
            }
            for rid, prem, conc, av in rows
        ],
    }


# ---- Pydantic validation ------------------------------------------------


class TestValidation:
    def test_loads_minimal_evaluation(self) -> None:
        data = _minimal_eval_dict(
            {"row-0": "good", "row-1": "good", "row-2": "good", "row-3": "bad"}
        )
        e = Evaluation.model_validate(data)
        assert e.id == "run-0001"
        assert e.benchmark_id == "stop-sign-example-1"
        assert e.n == 4
        assert e.model.provider == "mock"
        # defaults applied
        assert e.endorsement_config.n_samples == 5
        assert e.endorsement_config.tie_break == "abstain"
        assert e.framework_version  # populated from package __version__

    def test_rejects_invalid_tie_break(self) -> None:
        data = _minimal_eval_dict(
            {"row-0": "good", "row-1": "good", "row-2": "good", "row-3": "bad"}
        )
        data["endorsement_config"] = {"tie_break": "coinflip"}
        with pytest.raises(ValidationError):
            Evaluation.model_validate(data)

    def test_rejects_zero_n_samples(self) -> None:
        data = _minimal_eval_dict(
            {"row-0": "good", "row-1": "good", "row-2": "good", "row-3": "bad"}
        )
        data["endorsement_config"] = {"n_samples": 0}
        with pytest.raises(ValidationError, match="n_samples"):
            Evaluation.model_validate(data)


# ---- Endorsements view -> DerivedFrame ---------------------------------


class TestEndorsementsView:
    def test_endorsements_map_to_implications(self, stop_sign_bearers) -> None:
        data = _minimal_eval_dict(
            {"row-0": "good", "row-1": "good", "row-2": "good", "row-3": "bad"}
        )
        e = Evaluation.model_validate(data)
        endorsements = e.endorsements()

        # Row 3 is bad
        row3 = Implication.of(["sa", "ba"], ["ra"])
        assert endorsements[row3] == Verdict.BAD

        # Frame round-trip: rows 0-2 in, row 3 out
        frame = DerivedFrame.from_endorsements(stop_sign_bearers, endorsements)
        assert frame.contains(Implication.of(["sa"], ["ra"]))
        assert frame.contains(Implication.of(["sa", "n"], ["ra"]))
        assert frame.contains(Implication.of(["sa", "n", "nr"], ["ra"]))
        assert not frame.contains(Implication.of(["sa", "ba"], ["ra"]))


# ---- JSON round-trip ---------------------------------------------------


class TestJsonRoundtrip:
    def test_dumps_then_loads_equal(self) -> None:
        data = _minimal_eval_dict(
            {"row-0": "good", "row-1": "good", "row-2": "good", "row-3": "bad"}
        )
        e = Evaluation.model_validate(data)
        round_tripped = Evaluation.loads(e.dumps())
        assert round_tripped == e

    def test_dump_to_disk(self, tmp_path: Path) -> None:
        data = _minimal_eval_dict(
            {"row-0": "good", "row-1": "good", "row-2": "good", "row-3": "bad"}
        )
        e = Evaluation.model_validate(data)
        path = tmp_path / "eval.json"
        e.dump(path)
        assert Evaluation.load(path) == e

    def test_full_item_with_samples_round_trips(self) -> None:
        item = EvaluationItem(
            id="row-0",
            premises=["sa"],
            conclusions=["ra"],
            analyst_verdicts=[Verdict.GOOD],
            model_verdict=Verdict.GOOD,
            samples=[
                SampleRecord(
                    sample_index=i,
                    raw_response="GOOD",
                    parsed_verdict=Verdict.GOOD,
                    wall_time_ms=42.0,
                    finish_reason="stop",
                    reasoning_tokens=0 if i % 2 == 0 else 64,
                )
                for i in range(5)
            ],
            majority_vote=MajorityVote(good=5, bad=0, abstain=0, verdict=Verdict.GOOD),
        )
        e = Evaluation(
            id="run-with-samples",
            benchmark_id="stop-sign-example-1",
            benchmark_hash="sha256:deadbeef",
            model=ModelInfo(
                provider="mock",
                model_id="test-v1",
                params=ProviderParams(temperature=0.7, max_tokens=16),
            ),
            endorsement_config=EndorsementConfig(n_samples=5),
            started_at=datetime(2026, 5, 15, 8, 42, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 5, 15, 8, 42, 5, tzinfo=timezone.utc),
            items=[item],
        )
        round_tripped = Evaluation.loads(e.dumps())
        assert round_tripped == e
        assert round_tripped.items[0].samples[2].parsed_verdict == Verdict.GOOD
        assert round_tripped.items[0].samples[1].finish_reason == "stop"
        assert round_tripped.items[0].samples[1].reasoning_tokens == 64
        assert round_tripped.items[0].majority_vote is not None
        assert round_tripped.items[0].majority_vote.good == 5

    def test_budget_clipped_sample_round_trips(self) -> None:
        # A budget-clipped sample carries the new fields and the new
        # parse_status; round-trip preserves all of them.
        item = EvaluationItem(
            id="row-0",
            premises=["sa"],
            conclusions=["ra"],
            analyst_verdicts=[Verdict.GOOD],
            model_verdict=Verdict.ABSTAIN,
            samples=[
                SampleRecord(
                    sample_index=0,
                    raw_response="",
                    parsed_verdict=Verdict.ABSTAIN,
                    parse_status="budget_clipped",
                    finish_reason="length",
                    reasoning_tokens=1024,
                )
            ],
            majority_vote=MajorityVote(good=0, bad=0, abstain=1, verdict=Verdict.ABSTAIN),
        )
        e = Evaluation(
            id="run-budget",
            benchmark_id="x",
            model=ModelInfo(provider="mock", model_id="v1"),
            items=[item],
        )
        rt = Evaluation.loads(e.dumps())
        s = rt.items[0].samples[0]
        assert s.parse_status == "budget_clipped"
        assert s.finish_reason == "length"
        assert s.reasoning_tokens == 1024

    def test_premises_serialize_sorted(self) -> None:
        data = _minimal_eval_dict(
            {"row-0": "good", "row-1": "good", "row-2": "good", "row-3": "bad"}
        )
        e = Evaluation.model_validate(data)
        # row-3 premises in fixture: ["ba","sa"] (already sorted), but row-1 is ["n","sa"]
        # Verify deterministic output regardless of insert order
        text = e.dumps()
        round_tripped = Evaluation.loads(text)
        for orig, rt in zip(e.items, round_tripped.items, strict=True):
            assert orig.premises == rt.premises == sorted(rt.premises)
