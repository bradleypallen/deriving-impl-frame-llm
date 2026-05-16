"""``infereval metrics`` -- compute and report metrics from a saved evaluation.

Three output formats:

- ``text`` (default): plain prose summary for terminals.
- ``markdown``: tables suitable for embedding in reports.
- ``json``: machine-readable, the output of :meth:`MetricsReport.to_dict`.

Filters ``--by-tag`` and ``--by-rsr-target`` decompose the report by item
subset, matching the decomposition language of revised.tex Section 4. Each
filter takes the same reference (``--reference``) which defaults to
analyst consensus.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from infereval.benchmark import Benchmark
from infereval.evaluation import Evaluation
from infereval.metrics import (
    MetricsReport,
    analyst_reference,
    cohens_kappa,
    consensus_reference,
)

log = logging.getLogger(__name__)


FORMAT_CHOICES = ["text", "markdown", "json"]


def _parse_reference(spec: str, report: MetricsReport) -> tuple[str, object]:
    """Parse ``--reference`` spec into (label, ReferenceFn).

    ``consensus``      -> analyst consensus :math:`c_i`
    ``analyst:<id>``   -> single analyst by id (requires benchmark)
    ``analyst:<idx>``  -> single analyst by 0-based index
    """
    if spec == "consensus":
        return "consensus", consensus_reference(report.eta)
    if spec.startswith("analyst:"):
        rest = spec.removeprefix("analyst:")
        # Try numeric index first
        try:
            idx = int(rest)
        except ValueError:
            if report.benchmark is None:
                raise click.UsageError(
                    f"--reference analyst:{rest!r} requires --benchmark to resolve the analyst id"
                ) from None
            idx = report.benchmark.analyst_index(rest)
        return f"analyst[{idx}]", analyst_reference(report.eta, idx)
    raise click.UsageError(
        f"Unknown reference spec {spec!r}. Use 'consensus' or 'analyst:<id>' / 'analyst:<index>'."
    )


def _format_kappa(value: float | None) -> str:
    return "undefined" if value is None else f"{value:+.4f}"


def _format_text(
    report: MetricsReport,
    reference_label: str,
    kappa_C: float | None,
    *,
    title: str | None = None,
) -> str:
    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("=" * len(title))
    lines.append(f"n (items)              : {report.n}")
    lines.append(f"coverage (M)           : {report.coverage:.4f}")
    cov_per = report.coverage_per_analyst
    if cov_per:
        lines.append(
            "coverage (per analyst) : " + ", ".join(f"{c:.4f}" for c in cov_per)
        )
    lines.append(f"κ_C(η, {reference_label})       : {_format_kappa(kappa_C)}")
    lines.append(f"κ_F(η)                 : {_format_kappa(report.fleiss_kappa)}")
    lines.append(f"κ_F*(β) (inter-analyst): {_format_kappa(report.inter_analyst_fleiss)}")
    return "\n".join(lines)


def _format_markdown(
    report: MetricsReport,
    reference_label: str,
    kappa_C: float | None,
    *,
    title: str | None = None,
) -> str:
    lines: list[str] = []
    if title:
        lines.append(f"## {title}")
        lines.append("")
    lines.append("| metric | value |")
    lines.append("|---|---|")
    lines.append(f"| n | {report.n} |")
    lines.append(f"| coverage(M) | {report.coverage:.4f} |")
    cov_per = report.coverage_per_analyst
    if cov_per:
        per = ", ".join(f"{c:.4f}" for c in cov_per)
        lines.append(f"| coverage per analyst | {per} |")
    lines.append(f"| κ_C(η, {reference_label}) | {_format_kappa(kappa_C)} |")
    lines.append(f"| κ_F(η) | {_format_kappa(report.fleiss_kappa)} |")
    lines.append(f"| κ_F*(β) | {_format_kappa(report.inter_analyst_fleiss)} |")
    return "\n".join(lines)


def _format_json(
    report: MetricsReport,
    reference_label: str,
    kappa_C: float | None,
    *,
    title: str | None = None,
) -> str:
    out = report.to_dict()
    # Replace cohens_kappa_consensus with the actual reference label used.
    out.pop("cohens_kappa_consensus", None)
    out[f"cohens_kappa[{reference_label}]"] = kappa_C
    if title is not None:
        out["title"] = title
    return json.dumps(out, indent=2)


def _emit(
    report: MetricsReport,
    reference_label: str,
    reference_fn: object,
    output_format: str,
    *,
    title: str | None = None,
) -> None:
    kappa_C = cohens_kappa(report.eta, reference_fn)  # type: ignore[arg-type]
    if output_format == "text":
        click.echo(_format_text(report, reference_label, kappa_C, title=title))
    elif output_format == "markdown":
        click.echo(_format_markdown(report, reference_label, kappa_C, title=title))
    elif output_format == "json":
        click.echo(_format_json(report, reference_label, kappa_C, title=title))
    else:  # pragma: no cover -- defended by click.Choice
        raise click.UsageError(f"Unknown format {output_format!r}")


@click.command("metrics", help="Compute metrics from an evaluation JSON file.")
@click.argument("evaluation_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--benchmark",
    "benchmark_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Benchmark JSON. Required for --by-rsr-target, analyst-id references, and named coverage.",
)
@click.option(
    "--reference",
    "reference_spec",
    type=str,
    default="consensus",
    show_default=True,
    help="Reference for Cohen's kappa: 'consensus' or 'analyst:<id>' / 'analyst:<index>'.",
)
@click.option(
    "--by-tag",
    "tags",
    type=str,
    multiple=True,
    help="Repeat to add a per-tag decomposition.",
)
@click.option(
    "--by-rsr-target",
    "rsr_target_json",
    type=str,
    default=None,
    help='JSON of {"X": [...], "A": [...]} bearer-id sets. Requires --benchmark.',
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(FORMAT_CHOICES),
    default="text",
    show_default=True,
)
def metrics_cmd(
    evaluation_path: Path,
    benchmark_path: Path | None,
    reference_spec: str,
    tags: tuple[str, ...],
    rsr_target_json: str | None,
    output_format: str,
) -> None:
    """Compute and print metrics from a saved evaluation."""
    log.info("metrics.cli.start evaluation=%s benchmark=%s", evaluation_path, benchmark_path)

    try:
        eta = Evaluation.load(evaluation_path)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"ERROR: could not load evaluation: {exc}", err=True)
        sys.exit(2)

    bench: Benchmark | None = None
    if benchmark_path is not None:
        try:
            bench = Benchmark.load(benchmark_path)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"ERROR: could not load benchmark: {exc}", err=True)
            sys.exit(2)

    report = MetricsReport(eta=eta, benchmark=bench)
    reference_label, reference_fn = _parse_reference(reference_spec, report)

    # Overall
    _emit(report, reference_label, reference_fn, output_format, title="Overall")

    # By tag
    for tag in tags:
        click.echo("")
        sub = report.by_tag(tag)
        sub_label, sub_ref = _parse_reference(reference_spec, sub)
        _emit(sub, sub_label, sub_ref, output_format, title=f"By tag: {tag}")

    # By rsr-target
    if rsr_target_json is not None:
        if bench is None:
            click.echo(
                "ERROR: --by-rsr-target requires --benchmark to read rsr_target fields.",
                err=True,
            )
            sys.exit(2)
        try:
            spec = json.loads(rsr_target_json)
            X = frozenset(spec["X"])
            A = frozenset(spec["A"])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            click.echo(
                f"ERROR: --by-rsr-target must be JSON like "
                f'\'{{"X": ["sa"], "A": ["ra"]}}\': {exc}',
                err=True,
            )
            sys.exit(2)
        click.echo("")
        sub = report.by_rsr_target(X, A)
        sub_label, sub_ref = _parse_reference(reference_spec, sub)
        title = f"By RSR target: ⟨{{{','.join(sorted(X))}}}, {{{','.join(sorted(A))}}}⟩"
        _emit(sub, sub_label, sub_ref, output_format, title=title)

    log.info("metrics.cli.done evaluation=%s", evaluation_path)
