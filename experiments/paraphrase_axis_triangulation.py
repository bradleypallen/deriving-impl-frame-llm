"""Paraphrase-axis experiment across LLM families.

A worked example of the methodology in the paper, §5: vary the expression
function δ(ra) across three readings of "is red" (original, intrinsic,
perceptual) and measure each model's κ_C against Simonelli's analyst row.

The script supports an arbitrary list of (provider, model) pairs. The
default ``MODELS`` list covers six frontier families (Anthropic, OpenAI,
DeepSeek, Qwen, Gemini, Mistral) with a flagship and a distilled / small
variant from each, plus GPT-4.1 as the original-paper baseline.

Each model is skipped if its provider API key is missing in env. Each
``(model, variant)`` evaluation writes ``out/<slug>-<variant>.{json,jsonl}``
under ``--out-dir``; the script can be re-run incrementally as long as the
output directory is preserved (it will write fresh files but won't re-issue
already-completed sets unless rerun with the same out-dir, since each call
generates a new ``run_id``).

Findings from the first 3-model triangulation (2026-05-16, GPT-4.1 +
Claude Haiku 4.5 + DeepSeek v4-flash):

- **GPT-4.1** and **DeepSeek v4-flash** default to an *intrinsic* reading
  of ``a is red``: under the original phrasing they reproduce the paper's
  analyst row exactly (κ_C = +1.00).
- **Claude Haiku 4.5** defaults to a *perceptual* reading: under the
  original phrasing it treats nighttime and non-reflectivity as defeaters.
- All three models converge on the perceptual reading under the explicit
  ``a visibly appears red`` variant — they agree about defeasible inference;
  the disagreement was about δ.

Usage
-----

    # Requires API keys in env. Each model is skipped if its key is missing.
    export ANTHROPIC_API_KEY=sk-ant-...
    export OPENAI_API_KEY=sk-...
    export OPENROUTER_API_KEY=sk-or-...

    python experiments/paraphrase_axis_triangulation.py

    # Or run a single model:
    python experiments/paraphrase_axis_triangulation.py --only gpt-4.1

Outputs
-------

For each ``(model, variant)`` pair, writes:

- ``out/<model_slug>-<variant>.json``  — the Evaluation file (η).
- ``out/<model_slug>-<variant>.jsonl`` — the JSONL audit log.

Then prints a per-model verdict table, a per-model κ_C / κ_F table, and a
cross-model comparison table.

Notes
-----

- ``max_tokens=512`` is used here for historical continuity with the
  recorded fixtures. As of v0.5.2 the framework default is ``1024`` at
  both the Python API and the CLI, which also clears DeepSeek v4-flash's
  silent-reasoning-token consumption. At very low values like 32 tokens
  the ``content`` field comes back empty (``finish_reason=length``,
  ``reasoning_tokens=32``) and the framework records the resulting
  abstain as ``parse_status="budget_clipped"`` — a "ran out of budget"
  abstain rather than a model judgment.

- The defeasibility-explicit verification prompt below is used uniformly,
  with both system message and user template controlled. The 0.1.0
  benchmark JSON ``verification_prompt`` override only carries the user
  template, so we drop to the Python API for full control. See the related
  0.2.0 issue on adding ``system`` to the schema.
"""

from __future__ import annotations

import argparse
import copy
import os
import sys
from pathlib import Path
from typing import NamedTuple

from infereval.benchmark import Benchmark
from infereval.evaluation import EndorsementConfig, Evaluation, ProviderParams, evaluate
from infereval.metrics import MetricsReport
from infereval.prompts import VerificationPrompt
from infereval.providers import ProviderConfigError, get_provider
from infereval.providers.base import Provider

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = REPO_ROOT / "examples" / "stop_sign" / "benchmark.json"
DEFAULT_OUT_DIR = REPO_ROOT / "experiments" / "out"


# ---- Verification prompt (defeasibility-explicit) -----------------------


DEFEASIBLE_PROMPT = VerificationPrompt(
    id="defeasible-explicit-v1",
    system=(
        "You are evaluating whether an inference is materially good in everyday "
        "defeasible reasoning.\n\n"
        "This is NOT a question of strict deductive entailment. It is a question "
        "of defeasible material inference: granting typical background conditions "
        "and standard kinds, does the conclusion ordinarily follow from the "
        "premises?\n\n"
        "Answer with exactly one of: GOOD, BAD, ABSTAIN. No other text.\n\n"
        "GOOD means an ordinary reasoner would conclude this from the premises "
        "under default conditions.\n"
        "BAD means the premises positively rule out the conclusion (i.e., an "
        "explicit defeater is present in the premises).\n"
        "ABSTAIN means the question is ill-formed or you cannot judge.\n\n"
        "For example:\n"
        "  Premises: a is a bird\n"
        "  Conclusion: a can fly\n"
        "  Verdict: GOOD  (typical birds fly; the inference holds under default conditions)\n\n"
        "  Premises: a is a bird and a is a penguin\n"
        "  Conclusion: a can fly\n"
        "  Verdict: BAD  (the second premise is a defeater)"
    ),
    user_template="Premises: {premise_context}\nConclusion: {conclusion_context}\nVerdict:",
)


# ---- δ(ra) variants -----------------------------------------------------


VARIANTS: dict[str, str] = {
    "original":   "$a$ is red",
    "intrinsic":  "a has the standard color of stop signs",
    "perceptual": "a visibly appears red",
}


# ---- Models to triangulate ----------------------------------------------


class ModelSpec(NamedTuple):
    label: str
    provider_name: str
    model_id: str
    env_var: str
    extra_kwargs: dict[str, object]


_OPENROUTER_EXTRAS: dict[str, object] = {
    "http_referer": "https://github.com/bradleypallen/deriving-impl-frame-llm",
    "x_title": "infereval-paraphrase-axis-experiment",
}


MODELS: list[ModelSpec] = [
    # OpenAI baseline (the model Simonelli used in the paper).
    ModelSpec("gpt-4.1",          "openai",     "gpt-4.1",                       "OPENAI_API_KEY",     {}),
    # OpenAI current-generation pair (5.4).
    ModelSpec("gpt-5.4",          "openai",     "gpt-5.4",                       "OPENAI_API_KEY",     {}),
    ModelSpec("gpt-5.4-mini",     "openai",     "gpt-5.4-mini",                  "OPENAI_API_KEY",     {}),
    # Anthropic: Opus 4.7 flagship + Haiku 4.5 distilled tier.
    ModelSpec("claude-opus-4.7",  "anthropic",  "claude-opus-4-7",               "ANTHROPIC_API_KEY",  {}),
    ModelSpec("claude-haiku-4.5", "anthropic",  "claude-haiku-4-5-20251001",     "ANTHROPIC_API_KEY",  {}),
    # DeepSeek v4 pair.
    ModelSpec("deepseek-v4-pro",  "openrouter", "deepseek/deepseek-v4-pro",      "OPENROUTER_API_KEY", _OPENROUTER_EXTRAS),
    ModelSpec("deepseek-v4-flash","openrouter", "deepseek/deepseek-v4-flash",    "OPENROUTER_API_KEY", _OPENROUTER_EXTRAS),
    # Qwen: 3-max flagship + 3.6-flash distilled (slight generation gap).
    ModelSpec("qwen3-max",        "openrouter", "qwen/qwen3-max",                "OPENROUTER_API_KEY", _OPENROUTER_EXTRAS),
    ModelSpec("qwen3.6-flash",    "openrouter", "qwen/qwen3.6-flash",            "OPENROUTER_API_KEY", _OPENROUTER_EXTRAS),
    # Gemini 2.5 pair.
    ModelSpec("gemini-2.5-pro",   "openrouter", "google/gemini-2.5-pro",         "OPENROUTER_API_KEY", _OPENROUTER_EXTRAS),
    ModelSpec("gemini-2.5-flash", "openrouter", "google/gemini-2.5-flash",       "OPENROUTER_API_KEY", _OPENROUTER_EXTRAS),
    # Mistral pair.
    ModelSpec("mistral-large",    "openrouter", "mistralai/mistral-large-2512",  "OPENROUTER_API_KEY", _OPENROUTER_EXTRAS),
    ModelSpec("mistral-small",    "openrouter", "mistralai/mistral-small-2603",  "OPENROUTER_API_KEY", _OPENROUTER_EXTRAS),
]


# ---- Run helpers --------------------------------------------------------


def make_variant_benchmark(name: str, ra_expression: str) -> Benchmark:
    """Return the stop-sign benchmark with δ(ra) replaced by ``ra_expression``."""
    base = Benchmark.load(BENCHMARK_PATH).model_dump(mode="json")
    base["id"] = f"stop-sign-{name}"
    base["bearers"]["ra"]["expression"] = ra_expression
    return Benchmark.model_validate(base)


def run_one_variant(
    provider: Provider,
    bench: Benchmark,
    variant_name: str,
    model_slug: str,
    out_dir: Path,
    n_samples: int,
    max_tokens: int,
) -> Evaluation:
    """Evaluate ``provider`` against one δ(ra) variant, write η and log."""
    out_dir.mkdir(parents=True, exist_ok=True)
    eval_path = out_dir / f"{model_slug}-{variant_name}.json"
    log_path = out_dir / f"{model_slug}-{variant_name}.jsonl"
    config = EndorsementConfig(n_samples=n_samples)
    params = ProviderParams(temperature=0.0, max_tokens=max_tokens)
    eta = evaluate(
        bench,
        provider,
        config=config,
        params=params,
        verification_prompt=DEFEASIBLE_PROMPT,
        run_id=f"{model_slug}-{variant_name}",
        log_path=log_path,
    )
    eta.dump(eval_path)
    return eta


def run_model(
    spec: ModelSpec,
    out_dir: Path,
    n_samples: int,
    max_tokens: int,
) -> dict[str, Evaluation] | None:
    """Run all variants for one model; return dict[variant_name → Evaluation], or None if skipped.

    Per-variant evaluation failures are caught and logged so a single
    bad-model-id or rate-limit doesn't kill a multi-model sweep. The
    variant is dropped from the returned dict; the partial results from
    earlier variants are preserved.
    """
    import time

    if not os.environ.get(spec.env_var):
        print(f"[skip] {spec.label}: {spec.env_var} not set", file=sys.stderr)
        return None
    try:
        provider = get_provider(spec.provider_name, spec.model_id, **spec.extra_kwargs)
    except ProviderConfigError as exc:
        print(f"[skip] {spec.label}: {exc}", file=sys.stderr)
        return None

    print(f"\n=== {spec.label} ({spec.provider_name}:{spec.model_id}) ===")
    results: dict[str, Evaluation] = {}
    for variant_name, ra_expr in VARIANTS.items():
        print(f"    ... variant={variant_name}  δ(ra)={ra_expr!r}", flush=True)
        bench = make_variant_benchmark(variant_name, ra_expr)
        t0 = time.monotonic()
        try:
            results[variant_name] = run_one_variant(
                provider, bench, variant_name, spec.label, out_dir,
                n_samples=n_samples, max_tokens=max_tokens,
            )
            elapsed = time.monotonic() - t0
            print(f"        done in {elapsed:.1f}s", flush=True)
        except Exception as exc:  # noqa: BLE001 -- best-effort: keep sweeping
            elapsed = time.monotonic() - t0
            print(
                f"        FAILED after {elapsed:.1f}s: {type(exc).__name__}: {exc}",
                file=sys.stderr, flush=True,
            )
    if not results:
        # All variants failed for this model
        return None
    return results


# ---- Reporting ----------------------------------------------------------


def _kappa_str(value: float | None) -> str:
    return "undefined" if value is None else f"{value:+.4f}"


def _verdicts_per_item(results: dict[str, Evaluation]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for variant_name, eta in results.items():
        out[variant_name] = {it.id: it.model_verdict.value for it in eta.items}
    return out


def print_per_model_table(label: str, results: dict[str, Evaluation]) -> None:
    """Per-item verdicts and per-variant kappas for one model."""
    print(f"\n{label}")
    print("=" * len(label))
    rows = ["row-0", "row-1", "row-2", "row-3"]
    analyst = {
        it.id: it.analyst_verdicts[0].value
        for it in results["original"].items
    }
    print(f"{'item':6} {'analyst':9} {'original':10} {'intrinsic':10} {'perceptual':11}")
    print("-" * 56)
    by_variant = _verdicts_per_item(results)
    for rid in rows:
        cells = " ".join(f"{by_variant[v][rid]:10}" for v in ("original", "intrinsic", "perceptual"))
        print(f"{rid:6} {analyst[rid]:9} {cells}")

    print()
    print(f"{'variant':12} {'κ_C':10} {'κ_F':10}")
    print("-" * 36)
    for variant_name in ("original", "intrinsic", "perceptual"):
        r = MetricsReport(eta=results[variant_name])
        print(f"{variant_name:12} {_kappa_str(r.cohens_kappa()):10} {_kappa_str(r.fleiss_kappa):10}")


def print_cross_model_table(
    all_results: dict[str, dict[str, Evaluation]],
) -> None:
    """Cross-model side-by-side comparison."""
    if not all_results:
        return
    print()
    print("=" * 80)
    print("Cross-model comparison (κ_C vs analyst)")
    print("=" * 80)
    header = f'{"model":24} ' + " ".join(f"{v:>14}" for v in VARIANTS)
    print(header)
    print("-" * len(header))
    for model_label, results in all_results.items():
        cells = []
        for variant_name in VARIANTS:
            r = MetricsReport(eta=results[variant_name])
            cells.append(_kappa_str(r.cohens_kappa()))
        print(f'{model_label:24} ' + " ".join(f"{c:>14}" for c in cells))

    print()
    print("Per-item verdicts (analyst: good good good bad)")
    print("-" * 80)
    rows = ["row-0", "row-1", "row-2", "row-3"]
    for model_label, results in all_results.items():
        for variant_name in VARIANTS:
            verdicts = [
                next(it for it in results[variant_name].items if it.id == rid).model_verdict.value
                for rid in rows
            ]
            print(f"{model_label:24} {variant_name:12} {' '.join(f'{v:8}' for v in verdicts)}")


# ---- main ---------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--only", action="append", default=[],
        help="Run only the named model(s). Repeat for multiple. "
             f"Choices: {', '.join(m.label for m in MODELS)}",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUT_DIR.relative_to(REPO_ROOT)}/).",
    )
    parser.add_argument("--n-samples", type=int, default=3)
    parser.add_argument(
        "--max-tokens", type=int, default=2048,
        help="Per-sample max_tokens. 2048 is generous; needed for frontier "
             "reasoning-capable models (Gemini 2.5 Pro, Claude Opus, DeepSeek v4) "
             "that consume budget on silent internal reasoning.",
    )
    args = parser.parse_args(argv)

    selected = MODELS if not args.only else [m for m in MODELS if m.label in args.only]
    if args.only and not selected:
        print(f"ERROR: no models match --only {args.only}", file=sys.stderr)
        return 2

    all_results: dict[str, dict[str, Evaluation]] = {}
    for spec in selected:
        results = run_model(spec, args.out_dir, args.n_samples, args.max_tokens)
        if results is not None:
            all_results[spec.label] = results
            print_per_model_table(spec.label, results)

    print_cross_model_table(all_results)
    return 0 if all_results else 1


if __name__ == "__main__":
    sys.exit(main())
