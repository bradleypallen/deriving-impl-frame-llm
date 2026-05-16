"""``infereval evaluate`` -- run a model against a benchmark, write the evaluation JSON.

Wraps :func:`infereval.evaluation.evaluate` with click-level argument
parsing, provider construction, and ``--dry-run`` support (prints the
prompts that would be sent without calling the provider).

Threaded concurrency (``--workers``), JSONL run logs (``--log``), and
replay providers (``--replay-from``) land in M7 / M8.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import cast

import click

from infereval.benchmark import Benchmark
from infereval.context import resolve_context_builders
from infereval.evaluation import (
    EndorsementConfig,
    ProviderParams,
    TieBreak,
    evaluate,
)
from infereval.prompts import resolve_verification_prompt
from infereval.providers import (
    Provider,
    ProviderConfigError,
    ProviderError,
    get_provider,
)

log = logging.getLogger(__name__)

PROVIDER_CHOICES = ["anthropic", "openai", "openrouter"]
TIE_BREAK_CHOICES = ["abstain", "good", "bad", "first"]


def _print_dry_run(benchmark: Benchmark) -> None:
    """Build and print the per-item prompts without calling any provider."""
    from infereval.endorsement import _expressions_for

    prompt = resolve_verification_prompt(benchmark.verification_prompt)
    premise_builder, conclusion_builder = resolve_context_builders(
        benchmark.context_builders
    )
    bearers = benchmark.runtime_bearers()

    click.echo(f"# Dry run for benchmark {benchmark.id!r}")
    click.echo(f"# verification_prompt_id={prompt.id}")
    click.echo("")
    click.echo("## System prompt")
    click.echo(prompt.system)
    click.echo("")

    for item in benchmark.items:
        implication = item.to_implication()
        prem_exprs = _expressions_for(implication.premises, bearers, strip_tex=True)
        conc_exprs = _expressions_for(implication.conclusions, bearers, strip_tex=True)
        premise_ctx = premise_builder(prem_exprs)
        conclusion_ctx = conclusion_builder(conc_exprs)
        user_text = prompt.build_user(premise_ctx, conclusion_ctx)
        click.echo(f"## Item {item.id}")
        click.echo(user_text)
        click.echo("")


@click.command("evaluate", help="Run a model against a benchmark and write the evaluation JSON.")
@click.argument("benchmark_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--provider",
    "provider_name",
    type=click.Choice(PROVIDER_CHOICES, case_sensitive=False),
    help="LLM provider to use. Required unless --dry-run.",
)
@click.option(
    "--model",
    "model_id",
    type=str,
    help="Provider-specific model id (e.g. claude-opus-4-7, gpt-4o, anthropic/claude-3.5-sonnet).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to write the evaluation JSON. Required unless --dry-run.",
)
@click.option("--n-samples", type=click.IntRange(min=1), default=5, show_default=True)
@click.option("--temperature", type=float, default=1.0, show_default=True)
@click.option("--max-tokens", type=click.IntRange(min=1), default=32, show_default=True)
@click.option("--top-p", type=float, default=None)
@click.option("--seed", type=int, default=None,
              help="Random seed. Honored by OpenAI; ignored (with warning) by Anthropic.")
@click.option(
    "--tie-break",
    type=click.Choice(TIE_BREAK_CHOICES),
    default="abstain",
    show_default=True,
)
@click.option(
    "--strip-tex/--no-strip-tex",
    default=True,
    show_default=True,
    help="Strip $...$ TeX-math delimiters from bearer expressions at prompt time.",
)
@click.option(
    "--run-id",
    type=str,
    default=None,
    help="Stable id for this run. Generated as a UUID4 if not supplied.",
)
@click.option(
    "--log",
    "log_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path for the JSONL run log. One event per line; parseable with "
    "`jq` or `pandas.read_json(lines=True)`. Disabled if not given.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Build and print prompts; do not call any provider.",
)
@click.option(
    "--replay-from",
    "replay_from",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to a JSONL ReplayProvider fixture. When supplied, --provider "
    "and --model are ignored; the replay fixture drives all sample responses.",
)
@click.option(
    "--http-referer",
    type=str,
    default=None,
    help="OpenRouter attribution: HTTP-Referer header.",
)
@click.option(
    "--x-title",
    type=str,
    default=None,
    help="OpenRouter attribution: X-Title header.",
)
def evaluate_cmd(
    benchmark_path: Path,
    provider_name: str | None,
    model_id: str | None,
    output: Path | None,
    n_samples: int,
    temperature: float,
    max_tokens: int,
    top_p: float | None,
    seed: int | None,
    tie_break: str,
    strip_tex: bool,
    run_id: str | None,
    log_path: Path | None,
    dry_run: bool,
    replay_from: Path | None,
    http_referer: str | None,
    x_title: str | None,
) -> None:
    """Run a model against a benchmark and write the evaluation JSON."""
    log.info("evaluate.cli.start benchmark=%s dry_run=%s", benchmark_path, dry_run)

    try:
        benchmark = Benchmark.load(benchmark_path)
    except Exception as exc:  # noqa: BLE001 -- surface load error to user
        click.echo(f"ERROR: could not load benchmark: {exc}", err=True)
        sys.exit(2)

    if dry_run:
        _print_dry_run(benchmark)
        return

    provider: Provider
    if replay_from is not None:
        if output is None:
            click.echo("ERROR: --output is required.", err=True)
            sys.exit(2)
        try:
            from infereval.providers.mock import ReplayProvider

            provider = ReplayProvider(replay_from)
        except ProviderConfigError as exc:
            click.echo(f"ERROR: replay fixture: {exc}", err=True)
            sys.exit(2)
    else:
        if provider_name is None or model_id is None or output is None:
            click.echo(
                "ERROR: --provider, --model, and --output are required "
                "unless --dry-run or --replay-from is used.",
                err=True,
            )
            sys.exit(2)

        # Build the provider with provider-specific kwargs only when relevant.
        provider_kwargs: dict[str, object] = {}
        if provider_name.lower() == "openrouter":
            if http_referer is not None:
                provider_kwargs["http_referer"] = http_referer
            if x_title is not None:
                provider_kwargs["x_title"] = x_title

        try:
            provider = get_provider(provider_name, model_id, **provider_kwargs)
        except ProviderConfigError as exc:
            click.echo(f"ERROR: provider configuration: {exc}", err=True)
            sys.exit(2)

    config = EndorsementConfig(
        n_samples=n_samples,
        tie_break=cast(TieBreak, tie_break),
    )
    params = ProviderParams(
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        seed=seed,
    )

    try:
        eta = evaluate(
            benchmark,
            provider,
            config=config,
            params=params,
            strip_tex=strip_tex,
            run_id=run_id,
            log_path=log_path,
        )
    except ProviderError as exc:
        click.echo(f"ERROR: provider error during evaluation: {exc}", err=True)
        sys.exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    eta.dump(output)

    msg = (
        f"OK: wrote {output} "
        f"(run_id={eta.id!r}, items={eta.n}, samples_per_item={n_samples})"
    )
    if log_path is not None:
        msg += f"; log -> {log_path}"
    click.echo(msg)
    log.info(
        "evaluate.cli.done benchmark=%s output=%s run_id=%s",
        benchmark_path,
        output,
        eta.id,
    )
