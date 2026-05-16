"""``infereval describe <benchmark.json>`` -- print a benchmark summary.

Useful as the first step in working with a new benchmark: how many bearers,
items, analysts, and what the inter-analyst Fleiss baseline
:math:`\\kappa_F^*(\\beta)` looks like before any model is evaluated.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

import click

from infereval.benchmark import Benchmark
from infereval.metrics import inter_analyst_fleiss
from infereval.types import Verdict

log = logging.getLogger(__name__)


def _format_kappa(value: float | None) -> str:
    if value is None:
        return "undefined"
    return f"{value:+.4f}"


def _verdict_counts(verdicts: list[Verdict]) -> str:
    """Render a verdict tuple as ``g=3 b=1 a=0`` for compact tabular output."""
    counts = Counter(verdicts)
    return (
        f"g={counts.get(Verdict.GOOD, 0)} "
        f"b={counts.get(Verdict.BAD, 0)} "
        f"a={counts.get(Verdict.ABSTAIN, 0)}"
    )


@click.command("describe", help="Print a summary of a benchmark JSON file.")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def describe_cmd(path: Path) -> None:
    """Print a benchmark summary (id, |B|, |β|, m, label distribution, κ_F*)."""
    log.info("describe.start path=%s", path)
    bench = Benchmark.load(path)

    click.echo(f"id:          {bench.id}")
    if bench.title:
        click.echo(f"title:       {bench.title}")
    if bench.domain:
        click.echo(f"domain:      {bench.domain}")
    if bench.description:
        # Wrap long descriptions naturally; keep it simple.
        click.echo(f"description: {bench.description}")
    click.echo(f"schema:      {bench.schema_version}")
    click.echo("")
    click.echo(f"|B| (bearers):  {len(bench.bearers)}")
    click.echo(f"n (items):      {bench.n}")
    click.echo(f"m (analysts):   {bench.m}")
    click.echo("")

    # Per-analyst label distribution.
    click.echo("Per-analyst label distribution:")
    for j, analyst in enumerate(bench.analysts):
        verdicts = [item.analyst_verdicts[j] for item in bench.items]
        name = analyst.display_name or analyst.id
        click.echo(f"  [{j}] {analyst.id} ({name}): {_verdict_counts(verdicts)}")
    click.echo("")

    # Inter-analyst Fleiss baseline. Skip the call when m < 2 so the
    # metrics module's WARNING doesn't bleed into CLI output.
    if bench.m < 2:
        click.echo("κ_F*(β) (inter-analyst baseline): undefined")
        click.echo("  (undefined: requires m ≥ 2 analysts)")
    else:
        kappa_star = inter_analyst_fleiss(bench)
        click.echo(f"κ_F*(β) (inter-analyst baseline): {_format_kappa(kappa_star)}")
        if kappa_star is None:
            click.echo("  (undefined: analysts are unanimous or all-non-substantive)")
    click.echo("")

    # Tag frequencies, if any.
    tag_counts: Counter[str] = Counter()
    for item in bench.items:
        tag_counts.update(item.tags)
    if tag_counts:
        click.echo("Tags:")
        for tag, count in sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            click.echo(f"  {tag}: {count}")
        click.echo("")

    # RSR-targeted items, if any.
    rsr_targets = [item for item in bench.items if item.rsr_target is not None]
    if rsr_targets:
        click.echo(f"RSR-targeted items: {len(rsr_targets)} / {bench.n}")
        # Group by target
        by_target: dict[tuple[tuple[str, ...], tuple[str, ...]], int] = {}
        for item in rsr_targets:
            assert item.rsr_target is not None
            key = (
                tuple(sorted(item.rsr_target.X)),
                tuple(sorted(item.rsr_target.A)),
            )
            by_target[key] = by_target.get(key, 0) + 1
        for (X, A), count in sorted(by_target.items(), key=lambda kv: (-kv[1], kv[0])):
            click.echo(f"  ⟨{{{','.join(X)}}}, {{{','.join(A)}}}⟩: {count}")

    log.info("describe.ok path=%s", path)
