"""``infereval report`` — produce the construct-validity report.

Phase 3.1 of the construct-validity infrastructure (R16-R20). See
:mod:`infereval.report` for the underlying model and rendering.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from infereval.benchmark import Benchmark
from infereval.evaluation import Evaluation
from infereval.report import ConstructValidityClaims, render_markdown

log = logging.getLogger(__name__)


@click.command(
    "report",
    help="Produce a structured construct-validity report (R16-R20).",
)
@click.option(
    "--init-claims",
    "init_claims",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write a stub claims.json the analyst can fill in, then exit.",
)
@click.option(
    "--evaluation",
    "evaluation_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to the evaluation JSON. Required when --init-claims is not set.",
)
@click.option(
    "--benchmark",
    "benchmark_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to the source benchmark JSON. Required when --init-claims is not set.",
)
@click.option(
    "--claims",
    "claims_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to the analyst's claims JSON. Required when --init-claims is not set.",
)
@click.option(
    "--structure",
    "structure_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional: structural-coherence report JSON from `infereval structure`.",
)
@click.option(
    "--sweep",
    "sweep_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional: sensitivity-sweep summary JSON from `infereval sweep`.",
)
@click.option(
    "--model-fit",
    "model_fit_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional: factor-effects model fit JSON from `infereval model`.",
)
@click.option(
    "-o", "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Output path for the Markdown report. Defaults to stdout.",
)
@click.option(
    "--suppress-negatives",
    "suppress_negatives",
    is_flag=True,
    default=False,
    help="Suppress the Negative findings section. The fact of suppression "
    "is documented in the report header and the Summary verdict is "
    "downgraded one tier. The framework's normal posture is to surface "
    "negative findings by default.",
)
def report_cmd(
    init_claims: Path | None,
    evaluation_path: Path | None,
    benchmark_path: Path | None,
    claims_path: Path | None,
    structure_path: Path | None,
    sweep_path: Path | None,
    model_fit_path: Path | None,
    output: Path | None,
    suppress_negatives: bool = False,
) -> None:
    """Run the report builder; either emit a stub claims file or render the report."""
    if init_claims is not None:
        # Just write the stub and exit.
        stub = ConstructValidityClaims.stub()
        init_claims.parent.mkdir(parents=True, exist_ok=True)
        init_claims.write_text(stub.model_dump_json(indent=2) + "\n", encoding="utf-8")
        click.echo(f"OK: wrote stub claims file to {init_claims}")
        click.echo("Edit each FILL IN field, then run `infereval report` with the file via --claims.")
        return

    # Full report path.
    if not (evaluation_path and benchmark_path and claims_path):
        click.echo(
            "ERROR: --evaluation, --benchmark, and --claims are all required "
            "(unless --init-claims is supplied).",
            err=True,
        )
        sys.exit(2)

    try:
        evaluation = Evaluation.load(evaluation_path)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"ERROR: could not load evaluation: {exc}", err=True)
        sys.exit(2)

    try:
        benchmark = Benchmark.load(benchmark_path)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"ERROR: could not load benchmark: {exc}", err=True)
        sys.exit(2)

    if evaluation.benchmark_id != benchmark.id:
        click.echo(
            f"ERROR: evaluation references benchmark_id={evaluation.benchmark_id!r} "
            f"but the supplied --benchmark has id={benchmark.id!r}",
            err=True,
        )
        sys.exit(2)

    try:
        claims_raw = json.loads(claims_path.read_text(encoding="utf-8"))
        claims = ConstructValidityClaims.model_validate(claims_raw)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"ERROR: could not parse claims file: {exc}", err=True)
        sys.exit(2)

    markdown = render_markdown(
        evaluation=evaluation,
        benchmark=benchmark,
        claims=claims,
        structure_report=_load_optional_json(structure_path),
        sweep_summary=_load_optional_json(sweep_path),
        model_fit=_load_optional_json(model_fit_path),
        suppress_negatives=suppress_negatives,
    )

    if output is None:
        click.echo(markdown)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
        click.echo(f"OK: wrote {output}")
    log.info("report.cli.done evaluation=%s benchmark=%s", evaluation_path, benchmark_path)


def _load_optional_json(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data
