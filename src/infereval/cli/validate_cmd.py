"""``infereval validate`` -- structural validation of benchmark / evaluation files.

Validation is performed via the Pydantic models in :mod:`infereval.benchmark`
and :mod:`infereval.evaluation`, which subsume the JSON Schema (the Pydantic
``model_validator`` checks cross-field invariants like analyst-verdict tuple
length and unknown bearer references that pure JSON Schema cannot express).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click
from pydantic import ValidationError

from infereval.benchmark import Benchmark
from infereval.evaluation import Evaluation

log = logging.getLogger(__name__)


def _format_validation_error(exc: ValidationError) -> str:
    """Render a Pydantic ValidationError as a multi-line, human-readable string."""
    lines = [f"{len(exc.errors())} validation error(s):"]
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        lines.append(f"  - at {loc}: {err['msg']}")
    return "\n".join(lines)


@click.command("validate", help="Validate a benchmark or evaluation JSON file.")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--evaluation",
    "as_evaluation",
    is_flag=True,
    default=False,
    help="Validate as an evaluation (eta) file. Default is benchmark (beta).",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress success output; only print on failure.",
)
def validate_cmd(path: Path, as_evaluation: bool, quiet: bool) -> None:
    """Validate ``path`` as a benchmark (default) or evaluation file."""
    kind = "evaluation" if as_evaluation else "benchmark"
    log.info("validate.start path=%s kind=%s", path, kind)

    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        click.echo(f"ERROR: {path} is not valid JSON: {exc}", err=True)
        log.error("validate.json_decode_error path=%s err=%s", path, exc)
        sys.exit(2)

    try:
        if as_evaluation:
            obj: Benchmark | Evaluation = Evaluation.model_validate(raw)
        else:
            obj = Benchmark.model_validate(raw)
    except ValidationError as exc:
        click.echo(f"ERROR: {path} failed {kind} validation:", err=True)
        click.echo(_format_validation_error(exc), err=True)
        log.error("validate.failed path=%s kind=%s n_errors=%d", path, kind, len(exc.errors()))
        sys.exit(1)

    if not quiet:
        if isinstance(obj, Benchmark):
            click.echo(
                f"OK: {path} is a valid benchmark "
                f"(id={obj.id!r}, m={obj.m}, n={obj.n})"
            )
        else:
            click.echo(
                f"OK: {path} is a valid evaluation "
                f"(id={obj.id!r}, benchmark_id={obj.benchmark_id!r}, n={obj.n})"
            )
    log.info("validate.ok path=%s kind=%s", path, kind)
