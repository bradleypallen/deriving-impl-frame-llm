"""JSON Schemas (Draft 2020-12) for benchmark and evaluation files.

The Pydantic models in :mod:`infereval.benchmark` and :mod:`infereval.evaluation`
are the source of truth. This module exposes their JSON Schema projections
(via :meth:`pydantic.BaseModel.model_json_schema`) with the Draft 2020-12
``$schema`` and a stable ``$id`` set.

Two surfaces:

- :func:`benchmark_schema` / :func:`evaluation_schema` return the schema as a
  freshly-generated ``dict``.
- :func:`load_static_benchmark_schema` / :func:`load_static_evaluation_schema`
  read the committed JSON files shipped alongside this module. The committed
  files are what non-Python consumers should consume; the test suite asserts
  they stay in sync with what Pydantic generates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_BASE_ID = "https://allen.is/infereval/schema"

BENCHMARK_SCHEMA_PATH = Path(__file__).parent / "benchmark.schema.json"
EVALUATION_SCHEMA_PATH = Path(__file__).parent / "evaluation.schema.json"


def _augment(schema: dict[str, Any], schema_id: str, title: str) -> dict[str, Any]:
    """Decorate a Pydantic-generated schema with $schema, $id, and title headers."""
    return {
        "$schema": DRAFT_2020_12,
        "$id": schema_id,
        "title": title,
        **{k: v for k, v in schema.items() if k not in ("$schema", "$id", "title")},
    }


def benchmark_schema() -> dict[str, Any]:
    """Return the JSON Schema for benchmark files, generated from Pydantic."""
    from infereval.benchmark import Benchmark

    return _augment(
        Benchmark.model_json_schema(),
        schema_id=f"{SCHEMA_BASE_ID}/benchmark-1.0.json",
        title="infereval benchmark (beta)",
    )


def evaluation_schema() -> dict[str, Any]:
    """Return the JSON Schema for evaluation files, generated from Pydantic."""
    from infereval.evaluation import Evaluation

    return _augment(
        Evaluation.model_json_schema(),
        schema_id=f"{SCHEMA_BASE_ID}/evaluation-1.0.json",
        title="infereval evaluation (eta)",
    )


def load_static_benchmark_schema() -> dict[str, Any]:
    """Read the committed ``benchmark.schema.json`` shipped with the package."""
    with BENCHMARK_SCHEMA_PATH.open("r", encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
    return result


def load_static_evaluation_schema() -> dict[str, Any]:
    """Read the committed ``evaluation.schema.json`` shipped with the package."""
    with EVALUATION_SCHEMA_PATH.open("r", encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
    return result


def emit_static_schemas() -> None:
    """Regenerate the committed schema files from the current Pydantic models.

    Called by the ``infereval emit-schemas`` developer command and by the
    drift test (which writes to a tmp path and compares).
    """
    BENCHMARK_SCHEMA_PATH.write_text(
        json.dumps(benchmark_schema(), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    EVALUATION_SCHEMA_PATH.write_text(
        json.dumps(evaluation_schema(), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "BENCHMARK_SCHEMA_PATH",
    "DRAFT_2020_12",
    "EVALUATION_SCHEMA_PATH",
    "SCHEMA_BASE_ID",
    "benchmark_schema",
    "emit_static_schemas",
    "evaluation_schema",
    "load_static_benchmark_schema",
    "load_static_evaluation_schema",
]
