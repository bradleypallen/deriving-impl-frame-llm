"""Shared fixtures.

The ``stop_sign_*`` fixtures encode Example 1 of the paper
(Simonelli's stop-sign dialogue) as both runtime types and as a
:class:`infereval.benchmark.Benchmark` instance, so multiple test modules
can share one source of truth.

The ``build_evaluation`` helper constructs minimal :class:`Evaluation`
instances for metrics tests without going through the full ``evaluate``
pipeline.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from infereval.benchmark import Benchmark
from infereval.evaluation import Evaluation, EvaluationItem, ModelInfo, ProviderParams
from infereval.types import Bearer, Implication, Verdict


@pytest.fixture
def stop_sign_bearers() -> dict[str, Bearer]:
    """Bearers for Example 1: stop sign, red, nighttime, non-reflective, painted blue."""
    bearers = [
        Bearer(id="sa", expression="$a$ is a stop sign"),
        Bearer(id="ra", expression="$a$ is red"),
        Bearer(id="n", expression="it is nighttime"),
        Bearer(id="nr", expression="$a$ is not made with reflective material"),
        Bearer(id="ba", expression="$a$ has been painted blue"),
    ]
    return {b.id: b for b in bearers}


@pytest.fixture
def stop_sign_implications() -> dict[str, Implication]:
    """The four implications evaluated in Example 1."""
    return {
        "row-0": Implication.of(["sa"], ["ra"], id="row-0"),
        "row-1": Implication.of(["sa", "n"], ["ra"], id="row-1"),
        "row-2": Implication.of(["sa", "nr", "n"], ["ra"], id="row-2"),
        "row-3": Implication.of(["sa", "ba"], ["ra"], id="row-3"),
    }


@pytest.fixture
def stop_sign_endorsements(
    stop_sign_implications: dict[str, Implication],
) -> dict[Implication, Verdict]:
    """GPT-4.1's verdicts as recorded in Example 1 of the paper."""
    return {
        stop_sign_implications["row-0"]: Verdict.GOOD,
        stop_sign_implications["row-1"]: Verdict.GOOD,
        stop_sign_implications["row-2"]: Verdict.GOOD,
        stop_sign_implications["row-3"]: Verdict.BAD,
    }


@pytest.fixture
def stop_sign_benchmark_dict() -> dict:
    """Plain-dict form of the stop-sign benchmark for JSON / Pydantic tests."""
    return {
        "schema_version": "1.0",
        "id": "stop-sign-example-1",
        "title": "Stop-sign RSR (Example 1 of Allen 2026)",
        "domain": "everyday-physical-objects",
        "bearers": {
            "sa": {"expression": "$a$ is a stop sign"},
            "ra": {"expression": "$a$ is red"},
            "n": {"expression": "it is nighttime"},
            "nr": {"expression": "$a$ is not made with reflective material"},
            "ba": {"expression": "$a$ has been painted blue"},
        },
        "analysts": [{"id": "paper-author", "display_name": "Allen (Example 1 row)"}],
        "items": [
            {
                "id": "row-0",
                "premises": ["sa"],
                "conclusions": ["ra"],
                "analyst_verdicts": ["good"],
                "rsr_target": {"X": ["sa"], "A": ["ra"]},
                "tags": ["base-inference"],
            },
            {
                "id": "row-1",
                "premises": ["sa", "n"],
                "conclusions": ["ra"],
                "analyst_verdicts": ["good"],
                "rsr_target": {"X": ["sa"], "A": ["ra"]},
                "tags": ["irrelevant-addition", "nighttime"],
            },
            {
                "id": "row-2",
                "premises": ["sa", "nr", "n"],
                "conclusions": ["ra"],
                "analyst_verdicts": ["good"],
                "rsr_target": {"X": ["sa"], "A": ["ra"]},
                "tags": ["irrelevant-addition", "nonreflective"],
            },
            {
                "id": "row-3",
                "premises": ["sa", "ba"],
                "conclusions": ["ra"],
                "analyst_verdicts": ["bad"],
                "rsr_target": {"X": ["sa"], "A": ["ra"]},
                "tags": ["defeater", "painted-blue"],
            },
        ],
    }


@pytest.fixture
def stop_sign_benchmark(stop_sign_benchmark_dict: dict) -> Benchmark:
    """The stop-sign benchmark as a validated :class:`Benchmark`."""
    return Benchmark.model_validate(stop_sign_benchmark_dict)


def build_evaluation(
    *,
    rows: Sequence[tuple[Sequence[Verdict], Verdict]],
    item_ids: Sequence[str] | None = None,
    tags_per_row: Sequence[Sequence[str]] | None = None,
    benchmark_id: str = "test-bench",
    run_id: str = "test-run",
    premises_per_row: Sequence[Sequence[str]] | None = None,
    conclusions_per_row: Sequence[Sequence[str]] | None = None,
) -> Evaluation:
    """Build a minimal :class:`Evaluation` from ``(analyst_verdicts, model_verdict)`` rows.

    Designed for metrics tests: takes only the verdict data and fills the
    rest with sensible defaults (single-bearer ``["x"]`` premises and
    ``["y"]`` conclusions unless overridden, no samples, no majority-vote
    record).
    """
    items: list[EvaluationItem] = []
    for i, (analyst_verdicts, model_verdict) in enumerate(rows):
        item_id = item_ids[i] if item_ids is not None else f"row-{i}"
        tags = list(tags_per_row[i]) if tags_per_row is not None else []
        premises = (
            list(premises_per_row[i]) if premises_per_row is not None else ["x"]
        )
        conclusions = (
            list(conclusions_per_row[i]) if conclusions_per_row is not None else ["y"]
        )
        items.append(
            EvaluationItem(
                id=item_id,
                premises=premises,
                conclusions=conclusions,
                analyst_verdicts=list(analyst_verdicts),
                model_verdict=model_verdict,
                tags=tags,
            )
        )
    return Evaluation(
        id=run_id,
        benchmark_id=benchmark_id,
        model=ModelInfo(
            provider="mock",
            model_id="test-v1",
            params=ProviderParams(),
        ),
        items=items,
    )
