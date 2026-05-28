"""``infereval retest <eta_a.json> <eta_b.json>`` — test-retest reliability.

Compares two evaluations of the same benchmark and emits a
:class:`infereval.retest.RetestResult` artifact. The artifact is the
within-model analog of κ_F* (the inter-analyst peer baseline): it
quantifies how much of the headline κ_C is shared signal across
replications, vs. how much is run-specific noise. Required at scope
>= ``domain_D_as_sampled`` per R22; informational at narrower scope.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from infereval.benchmark import Benchmark
from infereval.evaluation import Evaluation
from infereval.report import ConstructValidityClaims
from infereval.retest import (
    RetestConfigMismatchError,
    compute_retest,
    retest_result_to_dict,
)

log = logging.getLogger(__name__)


@click.command(
    "retest",
    help=(
        "Compare two evaluations of the same benchmark to assess "
        "test-retest reliability (R22)."
    ),
)
@click.argument(
    "eta_a_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.argument(
    "eta_b_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--benchmark",
    "benchmark_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Optional benchmark JSON. When supplied, each flipped item is "
        "annotated with its factor levels so flips can be correlated "
        "with design factors."
    ),
)
@click.option(
    "--claims",
    "claims_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Optional claims JSON (the same file consumed by `infereval "
        "report`). When supplied, the analyst's declared identity "
        "criterion (from `reliability.identity_criterion`) is "
        "threaded into the RetestResult so the test-retest κ travels "
        "with what it's reliability-of. Required at scope >= "
        "domain_D_as_sampled to satisfy R22; the setup-conformance "
        "portion of the criterion is verified mechanically by the "
        "parity check on the two evaluation artifacts, while the "
        "analyst-substantiated portion (provider snapshot stability, "
        "scaffolding constancy) is recorded with caveats per the "
        "leakage-audit-gap pattern."
    ),
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Optional path to persist the RetestResult JSON. The report "
        "renderer (`infereval report --retest`) consumes this artifact "
        "to surface test-retest κ in section 2 and flipped items in "
        "section 4b (negative findings)."
    ),
)
def retest_cmd(
    eta_a_path: Path,
    eta_b_path: Path,
    benchmark_path: Path | None,
    claims_path: Path | None,
    output_path: Path | None,
) -> None:
    """Run the test-retest comparison and print a summary."""
    log.info(
        "retest.cli.start eta_a=%s eta_b=%s benchmark=%s",
        eta_a_path,
        eta_b_path,
        benchmark_path,
    )

    try:
        eta_a = Evaluation.load(eta_a_path)
        eta_b = Evaluation.load(eta_b_path)
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

    # v0.6.1: load the analyst's declared identity criterion from the
    # claims file when --claims is supplied. The criterion is what
    # makes the test-retest κ interpretable per Hlobil's individuation
    # point — without it, the κ is just a number; with it, the κ
    # explicitly travels with the standard it's reliability-of.
    identity_criterion = None
    if claims_path is not None:
        try:
            claims_raw = json.loads(claims_path.read_text(encoding="utf-8"))
            claims = ConstructValidityClaims.model_validate(claims_raw)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"ERROR: could not parse claims file: {exc}", err=True)
            sys.exit(2)
        if claims.reliability is not None:
            identity_criterion = claims.reliability.identity_criterion
        else:
            click.echo(
                "NOTE: --claims was supplied but the claims file does not "
                "declare reliability.identity_criterion; the retest will run "
                "without it, and the report's verdict gate may cap the "
                "verdict at scope >= domain_D_as_sampled.",
                err=True,
            )

    try:
        result = compute_retest(
            eta_a, eta_b, benchmark=bench, identity_criterion=identity_criterion
        )
    except RetestConfigMismatchError as exc:
        click.echo(f"ERROR: incompatible runs — {exc}", err=True)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"ERROR: unexpected failure during retest: {exc}", err=True)
        sys.exit(1)

    if output_path is not None:
        output_path.write_text(
            json.dumps(retest_result_to_dict(result), indent=2) + "\n",
            encoding="utf-8",
        )

    # Stdout summary.
    click.echo("test-retest reliability")
    click.echo("=======================")
    click.echo("")
    click.echo(f"benchmark:   {result.benchmark_id}")
    click.echo(f"run A:       {result.run_a_id}")
    click.echo(f"run B:       {result.run_b_id}")
    click.echo(f"items:       {result.n_items}")
    click.echo(
        f"agreement:   {result.n_agreements} "
        f"({result.agreement_rate * 100:.1f}%)"
    )
    click.echo(
        f"flips:       {result.n_disagreements} "
        f"({result.flip_rate * 100:.1f}%)"
    )
    if result.test_retest_kappa is None:
        click.echo("test-retest κ: undefined")
    else:
        click.echo(f"test-retest κ: {result.test_retest_kappa:+.4f}")
    click.echo("")

    if result.flipped_items:
        click.echo(f"Flipped items ({len(result.flipped_items)}):")
        for fi in result.flipped_items[:20]:  # cap noisy output
            fl_note = (
                f"  [{', '.join(f'{k}={v}' for k, v in fi.factor_levels.items())}]"
                if fi.factor_levels
                else ""
            )
            click.echo(
                f"  - {fi.item_id}: {fi.verdict_a} -> {fi.verdict_b}{fl_note}"
            )
        if len(result.flipped_items) > 20:
            click.echo(
                f"  ... ({len(result.flipped_items) - 20} more — see output JSON)"
            )
        click.echo("")

    click.echo(result.stability_verdict)
    log.info(
        "retest.cli.done n=%d agree=%d flips=%d kappa=%s",
        result.n_items,
        result.n_agreements,
        result.n_disagreements,
        result.test_retest_kappa,
    )
