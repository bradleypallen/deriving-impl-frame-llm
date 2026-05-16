"""Tests for ``infereval.schemas``.

Three things to guard:

1. The generated schemas are valid JSON Schema Draft 2020-12 (meta-schema check).
2. The static committed files (``benchmark.schema.json`` / ``evaluation.schema.json``)
   match what the Pydantic models currently generate -- i.e. no drift between
   the source of truth (Pydantic) and what we publish to non-Python consumers.
3. The committed stop-sign example validates against the benchmark schema using
   pure JSON Schema (so non-Python tools can also use the example file).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from infereval.schemas import (
    benchmark_schema,
    evaluation_schema,
    load_static_benchmark_schema,
    load_static_evaluation_schema,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STOP_SIGN_PATH = REPO_ROOT / "examples" / "stop_sign" / "benchmark.json"


# ---- Meta-schema validity --------------------------------------------------


class TestMetaSchema:
    def test_benchmark_schema_is_draft_2020_12(self) -> None:
        Draft202012Validator.check_schema(benchmark_schema())

    def test_evaluation_schema_is_draft_2020_12(self) -> None:
        Draft202012Validator.check_schema(evaluation_schema())

    def test_benchmark_schema_has_required_headers(self) -> None:
        s = benchmark_schema()
        assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert s["$id"].endswith("/benchmark-1.0.json")
        assert s["title"] == "infereval benchmark (beta)"

    def test_evaluation_schema_has_required_headers(self) -> None:
        s = evaluation_schema()
        assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert s["$id"].endswith("/evaluation-1.0.json")
        assert s["title"] == "infereval evaluation (eta)"


# ---- Static file drift -----------------------------------------------------


class TestStaticFilesInSync:
    """If these fail, run ``infereval.schemas.emit_static_schemas()`` to regenerate."""

    def test_static_benchmark_matches_generated(self) -> None:
        assert load_static_benchmark_schema() == benchmark_schema(), (
            "Static benchmark.schema.json is out of sync with Pydantic source. "
            "Regenerate via `python -c 'from infereval.schemas import "
            "emit_static_schemas; emit_static_schemas()'`."
        )

    def test_static_evaluation_matches_generated(self) -> None:
        assert load_static_evaluation_schema() == evaluation_schema(), (
            "Static evaluation.schema.json is out of sync with Pydantic source. "
            "Regenerate via `python -c 'from infereval.schemas import "
            "emit_static_schemas; emit_static_schemas()'`."
        )


# ---- Stop-sign example validates ------------------------------------------


@pytest.fixture(scope="module")
def stop_sign_json() -> dict:
    """Load the committed stop-sign benchmark JSON."""
    with STOP_SIGN_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


class TestStopSignExample:
    def test_validates_under_jsonschema(self, stop_sign_json: dict) -> None:
        # Pure-JSON-Schema validation -- the path a non-Python consumer would take.
        validator = Draft202012Validator(benchmark_schema())
        errors = sorted(validator.iter_errors(stop_sign_json), key=lambda e: list(e.path))
        assert errors == []

    def test_validates_under_pydantic(self, stop_sign_json: dict) -> None:
        from infereval.benchmark import Benchmark

        bench = Benchmark.model_validate(stop_sign_json)
        assert bench.id == "stop-sign-example-1"
        assert bench.m == 1
        assert bench.n == 4
        assert {it.id for it in bench.items} == {"row-0", "row-1", "row-2", "row-3"}
