# Changelog

All notable changes to `infereval` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the additional commitment that the benchmark and evaluation JSON
schemas are versioned independently (`schema_version: "1.0"`) and promised
stable from 1.0 onward, regardless of the framework version.

## [Unreleased]

Targeted for the 0.2.0 milestone. Provider compatibility patches landed
early during the cross-family experimentation (see below); core 0.2.0
items remain open.

### Added

- **`experiments/paraphrase_axis_triangulation.py` cross-family sweep**:
  the script's `MODELS` list now covers 13 frontier models from six
  families (Anthropic, OpenAI, DeepSeek, Qwen, Gemini, Mistral) plus
  GPT-4.1 as the original-paper baseline. The script auto-skips models
  whose API key is missing and isolates per-(model, variant) failures so
  one bad provider doesn't kill the sweep.
- **`experiments/results/` directory**: tracked location for committed
  findings artifacts, sibling to the gitignored `experiments/out/`
  working directory.
- **Cross-family findings document** at
  `experiments/results/cross_family_2026-05-18.md`. Eleven of thirteen
  frontier models reproduce Simonelli's analyst row exactly under the
  original δ(ra), an eleven-model independent replication. Includes all
  78 (Evaluation JSON + JSONL audit log) pairs from the sweep for full
  reproducibility.

### Fixed

- **OpenAIProvider**: route to `max_completion_tokens` for GPT-5.x and
  the o-series (o1, o3, o4) reasoning models; keep legacy `max_tokens`
  for pre-5.x models. OpenAI deprecated `max_tokens` for these families
  as of mid-2026, and the framework was silently failing every call
  against them. Closes #9.
- **AnthropicProvider**: skip the `temperature` parameter for Claude
  Opus 4.7 and later (the API rejects it as deprecated). Sonnet and
  Haiku still pass it through unchanged. Closes #10.

### Open (still in scope for 0.2.0)

- #4 — raise default `max_tokens` (still 32, too low for reasoning-capable
  models). The cross-family sweep used `max_tokens=2048` explicitly.
- #5 — surface `finish_reason` and `reasoning_tokens` on `SampleRecord`
  so budget-clipped and provider-side-failed samples are first-class
  distinguishable from genuine model abstentions at the η level.
- #6 — allow `system` override in benchmark JSON's `verification_prompt`
  field (the paraphrase-axis experiment still requires Python to
  override the system message).

## [0.1.0] — 2026-05-16

First public release. Implements the methodology of *Note on Simonelli's
Stop Sign Dialogue: An Implication-Space Methodology for the Empirical
Evaluation of LLM Inferential Mastery* (Allen, 2026).

### Added

- **Core data types** (`infereval.types`): `Verdict` enum
  (`good`/`bad`/`abstain`), frozen `Bearer` and `Implication` dataclasses
  with paper-faithful semantics (id-independent equality on implications,
  paraphrase families on bearers).
- **Derived implication frame** (`infereval.frame.DerivedFrame`): lazy
  membership per Definition 3 (clause (i) Containment ∪ clause (ii)
  endorsement); excludes ⟨∅, ∅⟩ by stipulation.
- **JSON I/O** (`infereval.benchmark`, `infereval.evaluation`): Pydantic
  models for benchmark (β) and evaluation (η) files with discriminated
  context-builder union (template + Python plugin), RSR-target metadata,
  cross-field validation (unknown bearer ids, mismatched analyst-verdict
  lengths). Sets serialize as sorted lists for diff-friendly output.
- **JSON Schemas** (`infereval.schemas`): Draft 2020-12 schemas for both
  file types, generated from the Pydantic models and committed at
  `src/infereval/schemas/{benchmark,evaluation}.schema.json` for non-Python
  consumers. Drift between source-of-truth and committed files is caught
  by a test.
- **Provider abstraction** (`infereval.providers`): `Provider` Protocol +
  `BaseProvider` ABC with retry-with-exponential-backoff-and-jitter.
  Concrete backends:
  - `AnthropicProvider` (Messages API) — emits a one-time warning when
    `seed` is supplied (Anthropic does not honor it).
  - `OpenAIProvider` (Chat Completions API) — passes `seed` through where
    the model supports it.
  - `OpenRouterProvider` — thin subclass of `OpenAIProvider` with
    OpenRouter base URL and optional `HTTP-Referer` / `X-Title` headers.
  - `ScriptedProvider` and `ReplayProvider` for deterministic testing.
  Lazy SDK imports so users only pay for the backends they install.
- **Endorsement pipeline** (`infereval.endorsement`): default verification
  prompt `default-v1` with `GOOD`/`BAD`/`ABSTAIN` tokens; regex parser
  with unparseable-as-abstain fallback; majority vote with deterministic
  tie-break (default `abstain`; configurable to `good`, `bad`, `first`);
  TeX-math delimiters stripped at prompt-construction time.
- **Metrics** (`infereval.metrics`): coverage, per-analyst coverage,
  analyst consensus, substantive index, Cohen's kappa, Fleiss' kappa,
  and the inter-analyst baseline `κ_F*(β)` from Remark 5. Edge cases
  (`m < 2`, unanimity, empty substantive subset, `p_e = 1`) return
  `None` with a warning rather than raising. `MetricsReport` aggregator
  with `by_tag` and `by_rsr_target` filters.
- **Structured JSONL logging** (`infereval.logging_setup`):
  `configure_run_logging` context manager attaches a JSONL `FileHandler`
  to the `infereval` logger for the duration of a run; per-sample audit
  records carry `prompt_hash`, `raw_response`, `parsed_verdict`,
  `parse_status`, `wall_time_ms`, and `usage`. One JSON object per line,
  consumable by `jq` or `pandas.read_json(lines=True)`.
- **CLI** (`infereval`): four subcommands — `describe`, `validate`,
  `evaluate`, `metrics`. The `evaluate` subcommand supports
  `--dry-run`, `--replay-from`, and `--log` for fully-deterministic
  audit-logged runs without API access. The `metrics` subcommand renders
  in `text`, `markdown`, or `json` and supports `--by-tag` and
  `--by-rsr-target` decompositions.
- **Stop-sign benchmark** at `examples/stop_sign/benchmark.json` (Example
  1 of the paper) plus a committed replay fixture at
  `tests/fixtures/stop_sign_replay.jsonl` (4 items × 5 samples) for the
  60-second quickstart.
- **Test suite**: 392 unit tests + 3 opt-in live-provider tests, 96.9%
  line coverage with a 90% threshold enforced via `pytest-cov`.

### Methodology defaults (locked in conversation; documented in `CLAUDE.md`)

- Package name: `infereval`. License: MIT.
- Verification prompt: fresh `default-v1` template (not a literal quote of
  prior work).
- `n_samples`: 5. Tie-break: `abstain` (matches the paper's treatment of
  abstention as the safe fallback). Cohen's kappa default reference:
  consensus `c_i`.
- δ / ctx_Γ / ctx_Δ placement: both JSON template form and Python plugin
  form supported.
- TeX-math delimiters (`$...$`) stripped at prompt-construction time.
- OpenAI surface: Chat Completions (for OpenRouter coverage).
- `κ_F*(β)` always reported by the CLI (as "undefined" when the
  baseline is unavailable per Remark 5).
- `DerivedFrame` materialization: lazy (membership via Def. 3 iff;
  the full I_M over ℘(B) × ℘(B) is unbounded).

### Deferred to a later release

- Async / batched provider calls (planned for 0.2.0; 0.1.0 is sequential
  by default for reproducibility).
- Bootstrap confidence intervals on metrics.
- Threaded `--workers > 1` concurrency for `evaluate`.

### Authors

- Bradley P. Allen, University of Amsterdam.

[0.1.0]: https://github.com/bradleypallen/deriving-impl-frame-llm/releases/tag/v0.1.0
