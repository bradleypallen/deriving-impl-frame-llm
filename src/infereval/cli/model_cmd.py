"""``infereval model <eta.json> --benchmark <bench.json>``.

CLI front-end for :mod:`infereval.modeling`. Fits a factor-effects
logistic regression of agreement on declared factor levels and prints
the coefficient table + per-factor joint Wald tests. Phase 2.2 of the
construct-validity infrastructure (R7, R12).
"""

from __future__ import annotations

import logging
import math
import sys
from pathlib import Path

import click

from infereval.benchmark import Benchmark
from infereval.evaluation import Evaluation
from infereval.modeling import ModelingError, fit_factor_model

log = logging.getLogger(__name__)


def _fmt_p(p: float) -> str:
    """Render a p-value with three stars at the conventional cutoffs."""
    if math.isnan(p):
        return "n/a"
    stars = ""
    if p < 0.001:
        stars = " ***"
    elif p < 0.01:
        stars = " **"
    elif p < 0.05:
        stars = " *"
    if p < 0.001:
        return f"< 0.001{stars}"
    return f"{p:.3f}{stars}"


def _fmt_coef(x: float) -> str:
    return f"{x:+.3f}" if not math.isnan(x) else "n/a"


@click.command(
    "model",
    help="Fit a factor-effects logistic regression of model–analyst agreement.",
)
@click.argument(
    "evaluation_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--benchmark",
    "benchmark_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Path to the source benchmark JSON. Required because the model "
    "uses `benchmark.factors` / `BenchmarkItem.factor_levels` (Phase 1.1).",
)
@click.option(
    "--reference",
    type=str,
    default="consensus",
    show_default=True,
    help="Reference column for the agreement outcome. 'consensus' uses "
    "the analyst-panel majority (abstain on tie); 'analyst:<id>' uses "
    "a single analyst column.",
)
def model_cmd(
    evaluation_path: Path,
    benchmark_path: Path,
    reference: str,
) -> None:
    """Fit the factor-effects model and print the report."""
    log.info(
        "model.cli.start evaluation=%s benchmark=%s",
        evaluation_path,
        benchmark_path,
    )

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
        fit = fit_factor_model(evaluation, benchmark, reference=reference)
    except ModelingError as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(2)

    click.echo("factor-effects model of agreement")
    click.echo("=================================")
    click.echo("")
    click.echo(f"evaluation:    {evaluation.id}")
    click.echo(f"benchmark:     {benchmark.id}")
    click.echo(
        f"observations:  {fit.n_observations} "
        f"(after excluding {fit.n_dropped_abstain} abstain sample(s))"
    )
    click.echo(f"items:         {fit.n_items}")
    click.echo(f"factors:       {fit.n_factors} declared")
    if fit.pseudo_r2 is not None:
        click.echo(f"pseudo-R²:     {fit.pseudo_r2:.3f}")
    click.echo("")

    # Per-factor joint Wald tests.
    click.echo("Per-factor joint Wald tests:")
    name_w = max(len(f) for f in fit.factor_wald)
    for f, p in fit.factor_wald.items():
        click.echo(f"  {f.ljust(name_w)}  {_fmt_p(p)}")
    click.echo("")

    # Effects table.
    click.echo("Effects (log-odds relative to baseline level):")
    if not fit.effects:
        click.echo("  (no non-baseline levels in fit)")
    else:
        f_w = max(len(e.factor) for e in fit.effects)
        l_w = max(len(e.level) for e in fit.effects)
        header = (
            f"  {'factor'.ljust(f_w)}  {'level'.ljust(l_w)}  "
            f"{'coef':>8}  {'SE':>6}  {'p':>10}  95% CI"
        )
        click.echo(header)
        for e in fit.effects:
            ci = f"[{e.conf_int_low:+.2f}, {e.conf_int_high:+.2f}]"
            click.echo(
                f"  {e.factor.ljust(f_w)}  {e.level.ljust(l_w)}  "
                f"{_fmt_coef(e.coef):>8}  {e.std_err:>6.3f}  "
                f"{_fmt_p(e.p_value):>10}  {ci}"
            )
    click.echo("")

    # Methodology notes.
    click.echo("Methodology:")
    for note in fit.notes:
        click.echo(f"  {note}")
    log.info("model.cli.done n_obs=%d pseudo_r2=%r", fit.n_observations, fit.pseudo_r2)
