# Changelog

All notable changes to `infereval` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the additional commitment that the benchmark and evaluation JSON
schemas are versioned independently (`schema_version: "1.0"`) and promised
stable from 1.0 onward, regardless of the framework version.

## [Unreleased]

No changes yet.

## [0.5.9] — 2026-05-23

Docs-only patch. Converts the four remaining relative links in the
README to absolute GitHub URLs so they resolve on the PyPI project
page. Caught while inspecting the v0.5.8 TestPyPI publication: PyPI
does not rewrite relative `LICENSE` / `CHANGELOG.md` / `experiments/...`
paths the way GitHub does, so the badge and inline links rendered as
404s. v0.5.8 had already converted the `docs/*.md` bullet list to
absolute URLs; this release closes the loop on the rest.

### Changed

- **`README.md`** — four link href fixes, all to
  `https://github.com/bradleypallen/infereval/blob/main/...`:
  - **License badge** href (was the broken one the user spotted on the
    v0.5.8 TestPyPI page).
  - **`[CHANGELOG](CHANGELOG.md)`** in the Status section.
  - **`[experiments/results/cross_family_2026-05-18.md]`** in the
    Findings section.
  - **`[LICENSE](LICENSE)`** in the bottom License section.
- **`CLAUDE.md`** — refreshed the release-flow note: `~/.pypirc`
  actually has both `[testpypi]` and `[pypi]` index-servers wired to
  `__token__` (twine picks them up non-interactively); added the
  absolute-URLs-only requirement to the release-hygiene check, with
  the 0.5.7 → 0.5.8 → 0.5.9 sequence as the worked example for why it
  matters.

### Note

No code, API, or schema-content change. `framework_version` default
in `evaluation.schema.json` bumped to `0.5.9`. `src/infereval/` is
byte-identical to v0.5.7/v0.5.8 apart from the `__version__` string.

## [0.5.8] — 2026-05-23

Docs-only patch. Rolls the post-`v0.5.7` documentation work into a
shippable release so the PyPI project page renders correctly: the
prior README pointed at relative `docs/*.md` paths that resolve on
GitHub but break on PyPI. This release replaces those with absolute
URLs to the live MkDocs Material docs site, and bundles the docs-site
infrastructure that the new links point at.

### Changed

- **`README.md`** — added a "Docs" CI badge and a prominent
  documentation-site pointer at the top. Replaced the bullet list of
  relative `docs/concepts.md`-style links (which 404 on PyPI) with a
  paragraph of absolute `https://www.bradleypallen.org/infereval/…`
  links. This is what fixes the PyPI project-page rendering.

### Added

- **MkDocs Material docs site** (`mkdocs.yml`, `.github/workflows/docs.yml`)
  — live at <https://www.bradleypallen.org/infereval/>, deployed from
  `main` on push.
- **New docs pages** (`docs/api.md`, `docs/architecture.md`,
  `docs/glossary.md`, `docs/schemas.md`) — auto-rendered API reference
  (mkdocstrings), Mermaid dataflow diagram, paper-symbol glossary, and
  schema field reference. Existing pages refreshed for the site.

### Note

No code, API, or schema-content change. `framework_version` default in
`evaluation.schema.json` bumped to `0.5.8`. The `src/infereval/`
package is byte-identical to v0.5.7 apart from the `__version__`
string.

## [0.5.7] — 2026-05-22

Catches three pieces of PyPI-surfaced metadata that still carried the
pre-Remark-8 "measure mastery" framing and the pre-`PR #60` Alpha
maturity descriptor. Cut as a follow-up to 0.5.6 because these are
baked into the wheel METADATA (and so into the PyPI project page)
rather than just the rendered README.

### Changed

- **`pyproject.toml` description (PyPI Summary)** — *"…derive
  implication frames and measure mastery against analyst-labeled
  benchmarks"* → *"…measure model–analyst agreement on labeled
  inference benchmarks. Evidence bearing on inferential-mastery
  attribution."* This line renders directly under the project name
  on PyPI.
- **`pyproject.toml` trove classifier** — `"Development Status ::
  3 - Alpha"` → `"4 - Beta"`, matching the README Status line
  corrected in 0.5.6.
- **`src/infereval/__init__.py` module docstring** — same
  measurement-vs-evidence framing fix, with an explicit pointer to
  Remark 8 of the paper. Shown by `help(infereval)`.

### Note

No behavior, API, or schema-content change. `framework_version`
default in `evaluation.schema.json` bumped to `0.5.7`.

## [0.5.6] — 2026-05-22

> **Superseded by 0.5.7 before publication.** The `v0.5.6` tag was created and
> wheels were built locally, but a follow-up pass caught three
> wheel-METADATA strings (the PyPI Summary, the `Development Status` trove
> classifier, and the module docstring) that still carried the pre-Remark-8
> "measure mastery" framing. Rather than force-move the just-cut tag, those
> fixes were rolled into 0.5.7 and that's the version that shipped. The
> `v0.5.6` tag has been retired; the entry is preserved here as the historical
> record of what 0.5.6 was going to be, since 0.5.7's notes reference it.

Release-hygiene patch. Bundles the README, CI, and documentation changes
that landed after the `v0.5.5` tag so the first PyPI publication
launches with the current state of the repository, not a snapshot that
predates the post-tag fixups.

### Changed

- **README Status line** — replaced the never-bumped `"Alpha (0.1.0)"`
  placeholder (verbatim from the 0.1.0 commit) with `"Beta (0.x,
  pre-1.0)"`, de-pinned so it can't drift again; points readers to the
  CHANGELOG for the current release.
- **README badges** — added CI status, GitHub release version, PyPI
  version, Python 3.10+, and MIT license badges to the header.

### Added

- **`.github/workflows/ci.yml`** — first GitHub Actions workflow. Runs
  `ruff check src tests`, `mypy src/infereval`, and `pytest -q` on
  every push to `main` and every PR (Python 3.12). Test/lint only —
  no build, no publish; PyPI upload remains a manual `twine` step.
- **Documentation of the leakage-audit gap** — `closing_the_construct_validity_gap.md`
  R8 and R9 each carry a "Known gap (deferred)" subnote describing
  the missing cross-check between the `held_out_items_used` /
  `training_data_separation_verified` boolean claims and the per-item
  `construction_metadata` that should substantiate them. The Phase 5
  checklist in `construct_validity_workflow.md` carries a matching
  caveat: until the v0.5.3-style audit cap lands for these claims,
  "your honesty in setting these booleans is the audit."

### Fixed

- **Latent `ruff N817` in the AR2 rationale test** (`Verdict` aliased
  to `V`) — switched to the already-imported `Verdict` so the new CI
  workflow starts green on day one.

### Note

No behavior, API, or schema-content change. `framework_version`
default in `evaluation.schema.json` bumped to `0.5.6`.

## [0.5.5] — 2026-05-21

Documentation-conformance release. Brings all cross-references into line
with the **revised** stop-sign note (21 May 2026), which changed its
title and renumbered both Definitions and Remarks. No behavior, API, or
schema changes — the formal content (Definitions 1–10, the RSR /
Containment machinery, and the kappa math) was already implemented
exactly as specified; only the citations and framing needed updating.

### Changed

- **Paper title** updated throughout (README prose + BibTeX, CLAUDE.md,
  the references list in `closing_the_construct_validity_gap.md`, and the
  citation string in `examples/pulmonary_edema/benchmark.json`):
  *"…An Implication-Space Methodology for the Empirical Evaluation of LLM
  Inferential Mastery"* → *"…An Implication-Space Instrument for Probing
  LLM Endorsement of Material Inferential Rules"*.
- **Definition citations** corrected for the revised numbering
  (6 Coverage, **7 Substantive index**, 8 Consensus, 9 Cohen, 10 Fleiss):
  `consensus_verdict` now cites Definition 8 (was 7); the Fleiss `S_F`
  filtering cites Definition 10 (was 9), with the substantive-index
  restriction `S` attributed to Definition 7.
- **Remark citations** corrected for the revised numbering: the κ_F\*
  baseline / `m<2` / non-unanimous conditions now cite Remark 4 (was 5);
  the paraphrase axis cites Remark 9 (was 8/6); carving-indexed
  in-principle claims cite Remark 10 (was 9). RSR-targeted citations
  (Remark 5) are unchanged — still correct.
- **README framing** aligned with the paper's Remark 8: the tagline now
  describes the framework as measuring the model's *agreement* with the
  benchmark, with that agreement framed as **evidence bearing on** an
  inferential-mastery attribution rather than a measurement of mastery.

### Note

The revised paper instantiates single-bearer succedents
(`⟨Γ, {ψ}⟩`); `infereval` continues to permit multi-element
`conclusions` lists (the multisuccedent generalization the paper
defers). This is a pre-existing, intentional superset, unchanged here.

## [0.5.4] — 2026-05-20

Analyst-side rationale support. New optional, additive schema field
that captures the natural-language reason each analyst gave for their
verdict, with positional alignment to ``analyst_verdicts``. Model-side
rationale elicitation is deferred to a later stage.

### Added

- **`BenchmarkItem.analyst_rationales: list[str] | None`** —
  per-analyst, per-item rationale text. Positionally aligned to
  ``analyst_verdicts``: index ``j`` is analyst ``j``'s rationale.
  ``None`` (the default and back-compat case) means "this benchmark
  carries no rationale discipline." A present list with an empty-string
  entry means "this analyst gave a verdict but recorded no reason on
  this item" — semantically distinct from ``None``. When the field is
  present, the length must equal ``len(benchmark.analysts)`` (enforced
  in ``Benchmark._check_consistency``). The framework validates
  structure and length only; rationale content is the analyst's
  responsibility (consistent with the framework's posture on
  ``construction_metadata`` and verdicts themselves).
- **`EvaluationItem.analyst_rationales: list[str] | None`** — propagated
  from the source benchmark item at evaluation-build time. Falls under
  the existing ``Evaluation.benchmark_hash`` integrity mechanism: a
  rationale cannot be silently altered between evaluation and report
  without changing the hash.
- **`infereval describe --items` rendering** — when rationales are
  present, the per-item block now lists each analyst's rationale text;
  an empty-string entry renders as ``(no reason recorded)`` so it's
  visually distinct from the absent-field case. Items where analysts
  disagree in verdict *and* carry rationales are flagged with
  ``⚠ disagreement+rationales`` on the header line — those are the
  noise-vs-signal triage targets for downstream disagreement diagnosis.
- **JSON schemas** — both ``benchmark.schema.json`` and
  ``evaluation.schema.json`` gain the optional ``analyst_rationales``
  array (``items: string``), with a description that states the
  positional-alignment contract and the ``null``-vs-empty-string
  distinction so external tooling and hand-authors get it right.
- 23 new tests across ``test_benchmark_io.py::TestAnalystRationales``
  and a new ``test_analyst_rationales_propagation.py`` covering all
  12 acceptance requirements (AR1–AR12): length mismatch rejection
  with the right error, backward compatibility against the existing
  stop-sign benchmark, the ``None``-vs-empty-string round-trip
  distinction, carry-through into the evaluation artifact, hash
  coverage, regression assertions that ``coverage`` / ``κ_C`` / ``κ_F``
  / ``κ_F*`` / structure-check outputs are byte-identical with and
  without rationales (proving the metric path is untouched), describe
  rendering, the divergence flag firing on disagreement+rationales,
  and the divergence flag staying silent on disagreement-only.

### Backwards compatibility

- **Additive only.** Every pre-0.5.4 benchmark and evaluation continues
  to validate unchanged. The new field defaults to ``None`` and is
  dropped from JSON output via ``exclude_none=True``, so existing
  fixtures and round-trip equality are preserved.
- **Metric and structural-check outputs are byte-identical** with and
  without rationales present (regression tested in
  ``TestMetricsRegressionAR2``).
- **Hash unchanged for rationale-free benchmarks.** ``canonical_benchmark_hash``
  uses ``exclude_none=True``, so a ``None``-valued ``analyst_rationales``
  field is omitted from the hash input — pre-0.5.4 benchmarks hash to
  the same value they did under 0.5.3.

### Out of scope

Model-side rationale elicitation (verification-prompt changes, per-sample
rationale logging, the prompt-sensitivity control for whether eliciting
reasons perturbs verdicts) is deferred. The disagreement-diagnosis
tooling that consumes analyst rationales (cohort-finding, noise-vs-signal
triage) is also deferred — this release delivers the data substrate it
will read, not the diagnosis itself.

## [0.5.3] — 2026-05-20

External-review release. An independent code review identified one
design-level issue in the construct-validity layer plus one real crash
bug; this release addresses both, plus a doc/data drift on Anthropic
model naming and a feature suggestion that lets factor-level negative
findings be labelled by valence.

### Fixed

- **Issue #1 (design, construct-validity)** — `compute_verdict` now
  consults the structure report and benchmark passed by
  `render_markdown`, not just the claims file. Two new audit caps:
  1. If `structural_check_run=True` *and* the supplied structure
     report contains any anomaly, the structural check is treated as
     failing (the check *ran* but didn't *pass*). The verdict is
     capped at `partially_defensible` with a rationale line naming the
     anomaly count.
  2. If the benchmark has `m < 2` analysts *and* the claim's scope is
     `items_in_benchmark`, the verdict is capped at
     `partially_defensible` and the panel size is surfaced in the
     one-liner (κ_F\* is undefined and there is no independent reference
     column; agreement with one analyst cannot inherit the
     convergent-validity guarantee a green badge implies).
  Backwards-compatible: callers that don't pass the new optional
  arguments get the v0.5.2 behaviour plus a "verdict computed
  unaudited" rationale line. The rendered report always passes them.
- **Issue #2 (crash bug)** — `infereval.structure.rsr_role_consistency_check`
  and `base_case_stability_check` no longer raise `KeyError` when the
  evaluation is missing an item that the benchmark carries an
  `rsr_target` for. Partial evaluations (the natural output of
  `--paraphrase-cycle` per-variant runs, tag-filtered re-runs) now
  match the rest of the package's contract: missing items are skipped
  with a logged warning, not raised. `run_all_checks` against a partial
  evaluation completes cleanly.
- **Issue #3 (docs)** — `docs/providers.md` now lists `claude-opus-4-7`
  as the current Opus id (with a dated example, `claude-opus-4-7-20260201`)
  matching the artifact fixtures in `experiments/results/cross-family/`,
  and explains the `4.7` / `4-7` filename-vs-id convention.

### Added

- **Issue #4 (feature)** — new optional `Benchmark.factor_kinds: dict[str, "substantive" | "experimentally_controlled"]`.
  When set, `collect_negative_findings` labels each null Wald-test
  finding's valence: substantive nulls **weaken** the mastery claim
  (the model failed to differentiate where it should), controlled
  nulls **strengthen** it (content-not-form behavior on a paraphrase
  axis is the wanted outcome). Factors omitted from the map keep the
  historical neutral summary. Schema-additive (R7 / R12).
- Six new tests for the partial-evaluation guard; six new tests for
  the verdict audit caps; five new tests for `factor_kinds`. Suite is
  now 612 unit tests.

### Note

This release is **conservative on existing data**. A previously-shipped
report whose claims were `structural_check_run=True` and benchmark was
m=1 will now render `⚠️ partially defensible` instead of `✅ defensible`
— the verdict the framework should have rendered all along. If you've
made public claims off the prior verdict, re-render with v0.5.3 and
acknowledge the change in your write-up.

## [0.5.2] — 2026-05-20

Tiny but consequential default-alignment release. The CLI's `--max-tokens`
flag and the Python `ProviderParams.max_tokens` field now agree.

### Fixed

- **CLI `--max-tokens` default raised from 32 to 1024**, aligning with the
  Python API default. The previous CLI default (`32`) was a holdover from
  a pre-reasoning-token era; for any reasoning-capable model
  (DeepSeek v4-flash, OpenAI o-family, Qwen-thinking variants, Anthropic
  Opus 4.7+ extended thinking) it silently produced budget-clipped
  abstains unless the user remembered to pass `--max-tokens` explicitly.
  The framework already correctly classified those abstains as
  `parse_status="budget_clipped"` (since v0.2.0), so the impact was on
  novice users running the CLI with only the required flags.
- **Docstring on `infereval.evaluation.evaluate`** corrected: the default
  `ProviderParams()` is `(temperature=1.0, max_tokens=1024)`, not
  `max_tokens=32` as the docstring previously claimed.
- **Documentation cleanup** following from the default alignment:
  `docs/providers.md` no longer carries the "CLI/API default mismatch"
  callouts; `docs/authoring_benchmarks.md`, the
  `paraphrase_axis_triangulation.py` docstring, and tutorial 03 now
  reference the current 1024 default rather than the historical 32
  footgun.

### Note

This is a behavior change for CLI invocations that omit `--max-tokens` —
the provider will be asked for up to 1024 tokens per sample instead of 32.
For typical one-word verdict prompts the difference is invisible (both
return after ~6 output tokens). For reasoning-capable models that consume
budget on silent internal reasoning, evaluations that previously
budget-clipped will now complete normally.

## [0.5.1] — 2026-05-20

**The construct-validity infrastructure series closes.** Final piece —
negative-results aggregation in the report (R21). Per the source
document, this is the construct-validity infrastructure working at
the reporting level: easy to surface failures by default, expensive to
hide them.

### Added

- **Issue #46 (Phase 3.2)** — **negative-results aggregation**.
  - New `collect_negative_findings(structure_report=…, sweep_summary=…,
    model_fit=…)` scans the three Phase 2 artifacts for findings that
    weaken or complicate the mastery claim:
    - Each structural anomaly is one finding.
    - Sweep instability (anything other than "stable") is one finding.
    - Each non-significant factor (Wald p > 0.05) is one finding.
  - **New Section 4b: Negative findings** in the rendered report.
    Renders one of four bodies depending on input:
    - "No Phase 2 artifacts supplied; the auto-collection step had
      nothing to scan."
    - "No negative findings detected in the supplied Phase 2 artifacts."
    - Grouped lists per source (structural anomalies / sweep
      instability / null factors).
    - When `--suppress-negatives` is set, a single banner explaining
      the suppression.
  - **New CLI flag `--suppress-negatives`** with three asymmetric
    side-effects:
    1. The Negative findings body is replaced by a suppression banner
       documenting the flag.
    2. A `Negative-findings suppression: ENABLED` warning is added to
       the report header (visible to any reader).
    3. The Summary verdict **downgrades one tier**: defensible →
       partially_defensible → not_defensible. Hiding evidence is
       itself a negative construct-validity signal.
  - 13 new tests across `collect_negative_findings` behavior, section
    rendering for the four input cases, the suppression banner, the
    header warning, the verdict downgrade, and CLI integration.

### Construct-validity infrastructure series closes

All nine features from *Closing the Construct-Validity Gap in
infereval* are now shipped:

**Phase 1 — schema and metadata**:
- v0.3.0 — factorial-design metadata (#30, R7+R12)
- v0.3.1 — runtime paraphrase-axis support (#32, R10)
- v0.3.2 — construction-provenance metadata (#34, R5+R8+R9)
- v0.3.3 — reference-panel declaration + cross-panel κ (#36, R4)

**Phase 2 — analytical extensions**:
- v0.4.0 — structural coherence checks (#38, R13)
- v0.4.1 — factor-effects model fitting (#40, R7+R12)
- v0.4.2 — sensitivity-analysis sweeps (#42, R11)

**Phase 3 — reporting and methodological discipline**:
- v0.5.0 — construct-validity report (#44, R16-R20)
- v0.5.1 — negative-results aggregation (#46, R21)

The remaining requirements that the document calls out as
*irreducibly outside the framework* — independent analyst panels,
held-out item construction, training-data separation, cross-domain
studies, replication, the in-principle interpretive commitments — are
research-program responsibilities the framework can make tractable
but not substitute for.

### Backwards compatibility

Pure-additive. No schema changes.

## [0.5.0] — 2026-05-20

**Phase 3 of the construct-validity infrastructure series begins.**
This release ships the *most opinionated* extension in the
programme per the source document: the construct-validity report
with structured claim slots. Closes coverage of **R16** (mastery
sense), **R17** (claim scope), **R18** (constitution vs. evidence),
**R19** (carving-indexed framing), and **R20** (disclosure of
analyst-supplied choices). The 0.x.y minor bump marks the
Phase-2-to-Phase-3 transition (analytical extensions →
reporting + methodological discipline).

### Added

- **Issue #44 (Phase 3.1)** — **construct-validity report**.
  - New module `infereval.report` with a `ConstructValidityClaims`
    Pydantic model (R16-R20) and a deterministic verdict computation:
    "defensible", "partially_defensible", or "not_defensible". The
    label is derived from the claimed scope + the
    competing-explanation-checks declared as run. The carving claim
    (R19) is required when scope reaches beyond `items_in_benchmark`.
  - **New CLI command** `infereval report`:
    - `--init-claims <path>` emits a stub claims JSON for the analyst
      to fill in.
    - With `--evaluation`, `--benchmark`, and `--claims`, plus
      optional `--structure`, `--sweep`, `--model-fit`, renders the
      report as Markdown to stdout or `--output <path>`.
  - The report has six sections: Identity, Summary metrics,
    Construct-validity claims (R16-R20), Evidence, Unaddressed
    competing explanations, Summary verdict. The Summary verdict
    renders one of three badges: ✅ defensible, ⚠️ partially
    defensible, ❌ not defensible. The framework refuses to render
    the ✅ badge without the corresponding competing-explanation
    checks marked as run.
  - 19 new tests across claims-schema validation, deterministic
    verdict computation (per scope tier), Markdown rendering (all
    six sections present, evidence integration, "NOT SUPPLIED"
    fallback), and CLI integration (`--init-claims`, full report,
    mismatched-id rejection).

  This is the most opinionated extension in the construct-validity
  programme per the source document — *embeds a methodological
  position about what claims should be made on top of what evidence*.
  The asymmetry: cheap to write up correctly (each slot has a clear
  format), expensive to write up incorrectly (the verdict
  deterministically downgrades when checks are missing or carving
  is unacknowledged at the wrong scope).

### Backwards compatibility

Pure-additive. New module, new CLI command. No schema changes.

## [0.4.2] — 2026-05-19

**Phase 2 of the construct-validity infrastructure series closes.**
Final Phase 2 piece adds sensitivity-analysis sweeps over varied
evaluation parameters. Addresses **R11** (sensitivity analysis on
free parameters).

### Added

- **Issue #42 (Phase 2.3)** — **sensitivity-analysis sweeps**.
  - New module `infereval.sweep` with `run_sweep(benchmark,
    provider, parameter, values, out_dir, ...)` and `coerce_values()`
    helpers.
  - **New CLI command** `infereval sweep <benchmark.json> --vary
    <param> --values <list> --provider X --model Y --out-dir <dir>`.
    Supported sweep parameters: `n_samples`, `tie_break`,
    `paraphrase_variant`, `temperature`. Each value produces a
    full per-value evaluation file + JSONL log; an aggregate
    `sweep-summary.json` carries the row table.
  - Dataclasses `SweepRow` and `SweepResult`; `SweepResult.stability_verdict`
    classifies the κ_C range into stable (< 0.05), moderate (< 0.10),
    or substantive variability — with escalating language so an
    unstable sweep tells the reader to consider tighter parameter
    choices or a wider analyst panel.
  - 18 new tests across value coercion, end-to-end sweep
    orchestration, the three stability-verdict bands, and the CLI
    integration.

### Phase 2 closes

All three Phase 2 features from *Closing the Construct-Validity Gap
in infereval* are now shipped:
- v0.4.0 — structural coherence checks (#38)
- v0.4.1 — factor-effects model fitting (#40)
- v0.4.2 — sensitivity-analysis sweeps (#42)

Phase 3 (reporting and methodological discipline — construct-validity
report + negative-results aggregation) is next.

### Backwards compatibility

Pure-additive. New module, new CLI command. No schema changes.

## [0.4.1] — 2026-05-19

Second piece of Phase 2 (analytical extensions). Adds factor-effects
modeling of model–analyst agreement against the design factors
declared in Phase 1.1. Addresses **R7** (multiple items per condition)
and deepens **R12** (per-condition decomposition).

### Added

- **Issue #40 (Phase 2.2)** — **factor-effects model fitting**.
  - New module `infereval.modeling` with `fit_factor_model(eval, bench)`
    producing a `ModelFit` containing per-level coefficients +
    per-factor joint Wald p-values + McFadden's pseudo-R² + the
    methodology notes.
  - Implementation: logistic regression of agreement
    (`sample.parsed_verdict == analyst_reference`) on declared
    factor levels, with **item-clustered standard errors** as a
    proxy for the per-item random-effect structure of a proper GLMM.
    The CLI / module / CHANGELOG explicitly call out the caveat:
    this is not a full GLMM (bambi/PyMC), but the marginal fixed-
    effects coefficients and joint Wald tests — which is what the
    document's "main effect of side-premise type, p < 0.001" output
    most directly needs — are recoverable.
  - **New CLI command** `infereval model <eta.json> --benchmark
    <bench>` prints the coefficient table, per-factor Wald tests,
    pseudo-R², and methodology notes.
  - Outcome reference: `--reference consensus` (default, analyst
    panel majority) or `--reference analyst:<id>` to pick a single
    analyst column.
  - 8 new tests covering: predictable factor detection, error on
    benchmark without declared factors, error on all-abstain
    dataset, pseudo-R² in unit interval, CLI integration, CLI
    error on mismatched benchmark id.

### Dependency

- New optional extra `[stats]`: `statsmodels>=0.14`. Install via
  `pip install 'infereval[stats]'`. The module imports it lazily so
  the rest of the framework works without it; importing
  `fit_factor_model` raises a clear `ModelingError` with the install
  hint if statsmodels is missing.

### Backwards compatibility

Pure-additive. New module, new CLI command, new optional extra.
No schema changes. No behavior change to existing commands.

## [0.4.0] — 2026-05-19

**Phase 2 of the construct-validity infrastructure series begins.**
Phase 2 covers analytical extensions beyond schema metadata —
structural coherence checks, mixed-effects model fitting, and
sensitivity-analysis sweeps. This release ships the *philosophically
central* piece: structural coherence checks against the derived frame
⟨B, I_M⟩. The 0.x.y minor bump marks the Phase 1→2 transition.

### Added

- **Issue #38 (Phase 2.1)** — **structural coherence checks on the
  derived frame**.
  - New module `infereval.structure` with three checks:
    - `containment_closure_check` — sanity-counts self-implications
      (items with Γ ∩ Δ ≠ ∅) and confirms they're in I_M by
      construction (clause i of Definition 3).
    - `rsr_role_consistency_check` — for items carrying an
      `rsr_target` and a role tag (`supporter`, `defeater`,
      `irrelevant-addition`), compares the model's verdict against
      the verdict the role *predicts* given the base-inference
      verdict on the same target. Flags items whose verdict
      contradicts the expected role-conditional verdict.
    - `base_case_stability_check` — surfaces targets where the model
      gives different verdicts on multiple base-inference items.
  - New dataclasses `StructuralAnomaly`, `StructuralCheck`,
    `StructuralReport`.
  - Top-level `run_all_checks(evaluation, benchmark)` runs all three
    and bundles the results.
  - **New CLI command** `infereval structure <eta.json> --benchmark
    <bench.json>` runs the checks and prints a human-readable report
    with per-section anomaly lists.
  - 16 new tests covering each check independently + the bundle + the
    CLI (including a live integration against the bundled pulmonology
    artifacts that correctly surfaces the a9 anomaly).

  Per *Closing the Construct-Validity Gap*: this is the addition that
  *converts the framework from agreement measurement to mastery
  characterization in the inferentialist sense* — the structural
  checks the Hlobil–Brandom framework explicitly motivates are now
  first-class operations.

### Backwards compatibility

Pure-additive: new module, new CLI command. No schema changes, no
behavior changes to existing commands.

## [0.3.3] — 2026-05-19

**Phase 1 of the construct-validity infrastructure series closes.**
Final Phase 1 piece adds reference-panel declaration and the
cross-panel agreement metric. Addresses **R4** (independent reference
check).

### Added

- **Issue #36 (Phase 1.4)** — **reference-panel declaration**.
  - `AnalystModel.panel: str | None = None` — analysts sharing a panel
    string are members of the same panel for cross-panel agreement
    analysis.
  - `Benchmark.primary_panel: str | None = None` — names the panel
    that `κ_F*` and the cross-panel statistic report against by
    default.
  - Validation: if any analyst declares a panel, all must (no
    partial-panel benchmarks); if `primary_panel` is set, at least one
    analyst must belong to it.
  - Helpers `Benchmark.panel_names()`, `analysts_in_panel(name)`,
    `analyst_indices_in_panel(name)`, `resolved_primary_panel()`.
  - **New metric** `inter_analyst_fleiss_per_panel(benchmark)` returns
    `κ_F*` per declared panel as `{panel_name: float | None}`.
  - **New metric** `cross_panel_kappa(benchmark, primary=..., check=...)`
    computes Cohen's κ between two panels' per-item consensus
    verdicts (majority within each panel, abstain on tie), restricted
    to items where both panels yield a substantive consensus. Guards
    against shared-error agreement within the primary pool (the
    specific concern Campbell & Fiske 1959 raise).
  - `inter_analyst_fleiss(benchmark)` now returns the *primary panel's*
    κ_F* for panelled benchmarks (unpanelled behavior unchanged).
  - **CLI**: `infereval describe` adds an `analyst panels:` section
    listing each panel's members, per-panel κ_F*, and (when exactly
    two panels are declared) the cross-panel κ_C. Omitted when no
    analyst declares a panel.
  - 14 new tests across schema validation, helpers, the per-panel +
    cross-panel metrics (with hand-verified κ value), and the CLI
    rendering.

### Backwards compatibility

`AnalystModel.panel` and `Benchmark.primary_panel` both default to
`None`. Every pre-0.3.3 benchmark validates unchanged.
`inter_analyst_fleiss(benchmark)` returns the same value as before
for flat benchmarks. `schema_version` stays `"1.0"`.

### Phase 1 closes

All four Phase 1 features from *Closing the Construct-Validity Gap in
infereval* are now shipped: factorial-design metadata (#30 / v0.3.0),
runtime paraphrase-axis support (#32 / v0.3.1), construction-provenance
metadata (#34 / v0.3.2), and reference-panel declaration (#36 / v0.3.3).
Phase 2 (analytical extensions — structural coherence checks, mixed-
effects model fitting, sensitivity-analysis sweeps) is next.

## [0.3.2] — 2026-05-19

Third piece of the construct-validity infrastructure series. Adds
per-item construction provenance for benchmark audit. Addresses partial
coverage of **R5** (documented construction), **R8** (held-out items),
and **R9** (training-data separation).

### Added

- **Issue #34 (Phase 1.3)** — **construction-provenance metadata**.
  - New `ConstructionMetadata` model with optional fields
    `authored_by`, `authored_on` (ISO date), `authored_blind_to_models`,
    and `source` (free-form citation for the primary material the
    author worked from — distinct from `references` which carries the
    framework-level `Reference` objects justifying the verdict).
  - `BenchmarkItem.construction_metadata: ConstructionMetadata | None`
    — `None` by default; populate selectively for items where the
    provenance matters.
  - `infereval describe` adds a `construction provenance:` summary
    section listing the annotated-item count, unique authors,
    authored-on date range, blinded-to model count, and source-citation
    count. Omitted when no item carries metadata.
  - `infereval describe --items` adds a `construction:` line per
    annotated item, rendering author + date + blinded-models + source
    on a single wrapped line. Omitted for items without metadata.
  - Content is the analyst's responsibility — the framework validates
    structure (Pydantic types, `extra="forbid"`) but does not enforce
    that `authored_on` post-dates any training cutoff. The point is
    to make the *presence* of these declarations auditable.

### Backwards compatibility

`BenchmarkItem.construction_metadata` defaults to `None`. Every
pre-0.3.2 benchmark validates unchanged. `schema_version` stays
`"1.0"`.

## [0.3.1] — 2026-05-19

Second piece of the construct-validity infrastructure series. Promotes
the `BearerModel.paraphrases` field from documentation-only to
runtime-active and exposes it on the CLI as `--paraphrase-variant` /
`--paraphrase-cycle`. Addresses **R10** — *the single most-cited
concern in the source document about content-vs-form sensitivity*.

### Added

- **Issue #32 (Phase 1.2)** — **runtime paraphrase-axis support**.
  - `infereval.endorsement._expressions_for(..., variant=k)` now picks
    `bearer.paraphrases[k-1]` per bearer for `k >= 1`, falling back to
    `bearer.expression` when the bearer doesn't have that paraphrase.
    `variant=0` (default) preserves existing behavior.
  - `infereval.endorsement.endorse(..., variant=k)` and
    `infereval.evaluation.evaluate(..., variant=k)` thread the variant
    through.
  - New `Evaluation.paraphrase_variant: int = 0` field records which
    variant was used at evaluation time.
  - New `Benchmark.n_paraphrase_variants -> int` helper returns
    `1 + max(len(b.paraphrases) for b in bearers)`.
  - **CLI**: `infereval evaluate` gains `--paraphrase-variant K` (single
    non-default variant) and `--paraphrase-cycle` (all K variants).
    Mutually exclusive. `--paraphrase-cycle` suffixes the output path,
    log path, and run-id with `-vN` per variant so the per-variant
    artifacts are unambiguous.
  - **CLI**: `infereval describe` adds a one-line `paraphrase variants:`
    summary when any bearer carries paraphrases (`K (Y/Z bearers carry
    paraphrases; max M each)`). Omitted otherwise.
  - Validation: `--paraphrase-variant K` rejects `K >=
    benchmark.n_paraphrase_variants`; the two flags together is
    rejected with a clear error.
  - 12 new unit tests covering `_expressions_for` variant semantics
    (canonical / first / second / out-of-range), the `evaluate()`
    integration (recording / round-trip / backwards-compat), the
    `n_paraphrase_variants` helper, CLI behaviors (variant recording,
    cycle file-suffixing, log-suffixing, run-id-suffixing, out-of-range
    rejection, mutual-exclusion rejection, no-effect on benchmarks
    without paraphrases), and the `describe` rendering (omitted /
    rendered with correct variant count and coverage line).

### Backwards compatibility

`Evaluation.paraphrase_variant` defaults to `0`. Every pre-0.3.1
evaluation JSON validates unchanged. No bearer-side schema changes —
`paraphrases` was already in the schema, just unused at runtime.
`schema_version` stays `"1.0"`.

## [0.3.0] — 2026-05-19

**Construct-validity infrastructure series begins.** First piece of the
multi-release programme set out in *Closing the Construct-Validity Gap
in infereval*, which extends the framework from "agreement
measurement" into the construct-validity-supporting role the
inferentialist methodology actually needs. Subsequent Phase-1 features
will be 0.3.x patch releases.

The 0.x.y minor bump marks the methodological shift in what `infereval`
sets out to be, not a breaking schema change — all 0.2.x benchmarks
validate unchanged.

### Added

- **Issue #30 (Phase 1.1)** — **factorial-design metadata**. New
  schema fields:
  - `Benchmark.factors: dict[str, list[str]]` — declared design factors
    and their levels for crossed-design benchmarks.
  - `Benchmark.factor_constraints: FactorConstraints | None` — currently
    supports `min_items_per_cell` (enforced by the model validator).
  - `BenchmarkItem.factor_levels: dict[str, str]` — per-item position
    in the design space.
  - New helpers `Benchmark.cells()` (count items per cell of the fully
    crossed design) and `Benchmark.is_fully_crossed_at_k(k)` (boolean).
  - Validation: every key in any item's `factor_levels` must be a
    declared factor; every value must be in the declared levels list;
    if `min_items_per_cell` is set, every cell must contain at least
    that many items.
  - **`infereval describe`** gains a `factorial design:` section
    summarising the factors, the crossed-cell count, the populated
    cell count, and (when declared) the `min_items_per_cell` floor
    with explicit underpopulated-cell list. Omitted when no factors
    declared.

  Addresses R7 (multiple items per condition) and supports R12
  (per-condition decomposition). 12 new unit tests on the schema
  validators + helpers, 3 new on the CLI rendering.

### Backwards compatibility

`factors`, `factor_constraints`, and `factor_levels` all default to
empty / `None`. Every pre-0.3.0 benchmark validates unchanged.
`schema_version` stays `"1.0"` — additive-with-defaults; existing
schema-version-1.0 consumers continue to work.

## [0.2.6] — 2026-05-19

CLI improvement release. Adds an expert-readable per-implication
listing mode to `infereval describe`.

### Added

- **Issue #28** — `infereval describe --items` (also `-i`). When
  supplied, prints every implication in a self-contained form a
  domain expert can read without opening the source JSON:
  - bearer-id form on the header line (links back to the methodology paper)
  - resolved English expressions for every premise (`Γ:`) and conclusion (`Δ:`)
  - analyst verdict (or m-tuple for multi-analyst benchmarks)
  - tag annotation in `[…]`
  - full inline reference block — citation + DOI + URL + section + note,
    each wrapped to 78 cols with continuation indent
  Items are grouped by target tag (`T1` / `T2` / `cross-cutting`) when
  those tags are present, otherwise rendered as a single flat block.
  Off by default so the summary stays compact for large benchmarks.
  Eight new unit tests cover the flag, the section header, resolved
  expressions, verdict rendering, inline references (including the
  pulmonology-benchmark `FLAG FOR PULMONOLOGIST REVIEW` annotation on
  a9), target-tag grouping with sort order, flat-list fallback for
  benchmarks without target tags, and the multi-analyst verdict tuple
  format.

## [0.2.5] — 2026-05-19

CLI improvement release. Makes `infereval describe` actually useful for
non-trivial benchmarks.

### Added

- **Issue #25** — `infereval describe` now surfaces four sections that
  were previously invisible:
  - **`verification prompt`** block (id, template, system message, parse
    regex) when the benchmark embeds a `VerificationPromptOverride`;
    omitted when the benchmark uses the framework default.
  - **`bearers (<n>)`** block listing every bearer id paired with its
    expression, two-column aligned, wrapping long expressions under the
    value column. Replaces the previous "you have to open the JSON to
    know what `cd` means" workflow.
  - **`references`** summary (counts at corpus / bearer / item levels;
    bearer-annotation ratio; mean refs per annotated item; the first 3
    corpus citations). Omitted entirely when no references field is
    populated. Closes the gap from Issues #18 / #22 — references are
    now visible in the primary inspection tool.
  - **`verdict distribution by tag group`** cross-tab. Scans each
    item's `tags` for the first target-inference identifier (`T1`,
    `T2`, …) or the literal `cross-cutting` tag; groups the analyst
    verdicts under those labels. Surfaces the per-target label balance
    the flat tag-frequency list cannot. Skipped when no item has a
    recognised group tag.

### Changed

- **Long `description` strings now wrap to 78 columns** (`textwrap.fill`
  with the value column aligned to the new fixed 13-char label gutter).
  Previously the description printed on a single physical line that
  wrapped awkwardly in any narrow terminal.
- **Header lines (`id` / `title` / `domain` / `description` / `schema`)
  now share a 13-char label column** so the values line up vertically.
  Visually consistent with the rest of the report.

### Tests

8 new unit tests in `tests/unit/test_cli_describe.py::TestDescribeNewSections`
cover all four new sections + the header-alignment regression boundary
+ section-omission behavior on benchmarks that don't carry the relevant
data.

## [0.2.4] — 2026-05-19

Single-issue patch release. Completes the references work begun in
v0.2.2 (Issue #18) by propagating benchmark-side provenance into the
evaluation artifact.

### Fixed

- **Issue #22** — `Evaluation` and `EvaluationItem` now carry a
  `references: list[Reference]` field, populated by `evaluate()` from
  the source benchmark's corresponding fields. Without this fix, all
  references on a benchmark (v0.2.2+) were dropped on the floor as soon
  as `evaluate()` ran, meaning anyone reading just an evaluation JSON
  file (the primary research artifact — what gets shared, archived,
  cited, replayed) had no readable provenance trail. The
  `benchmark_hash` confirms the source benchmark was the right one at
  run time but does not tell the reader *what guidelines* anchored each
  item. Five new unit tests in
  `tests/unit/test_evaluate.py::TestReferencesPropagation` cover the
  propagation path end-to-end: corpus-level refs, per-item refs,
  dump+load round-trip, the all-empty-defaults backwards-compatibility
  regression guard, and the string-shorthand auto-promotion at the
  evaluation level. Bearer-level references are intentionally not
  propagated by this fix because `Evaluation` does not currently carry
  any bearer data — that's its own design question and a separate
  change.

## [0.2.3] — 2026-05-19

Single-issue patch release. Restores correct evaluation behavior against
GPT-5.x and the o-series reasoning models when the caller asks for a
non-default temperature (e.g. ``temperature=0.0`` for determinism).

### Fixed

- **Issue #20** — `OpenAIProvider` now skips the ``temperature`` parameter
  for GPT-5.x and the o-series reasoning models (o1, o3, o4-*), which
  reject any value other than the default 1.0 with HTTP 400
  ``invalid_request_error``. Detection uses a new
  ``_rejects_temperature(model_id: str)`` predicate that matches the same
  model set as ``_uses_max_completion_tokens`` — same generation of
  models, same set of API constraints. The requested temperature is
  still recorded in ``ProviderParams`` and the evaluation JSON for
  audit-trail purposes (same posture as Anthropic's handling of ``seed``
  for ``claude-*``). Without this fix, any evaluation against
  ``gpt-5.x`` or an o-series model with ``--temperature 0.0`` (the
  default ``-o`` flag in our experimental scripts) had every sample
  return as ``parse_status: sample_failed`` and every item abstain.
  Six new unit tests in ``tests/unit/test_provider_openai.py`` cover
  the new predicate across the GPT-5 generation, the o-series, and the
  OpenRouter vendor-prefixed model id, plus a regression guard
  confirming GPT-4o and GPT-4.1 still accept ``temperature``.

## [0.2.2] — 2026-05-19

Schema feature release. Adds first-class provenance support for benchmarks.

### Added

- **Issue #18** — **`Reference` model** and `references: list[Reference]`
  field on three schema levels: `Benchmark`, `BearerModel`, and
  `BenchmarkItem`. Motivates regulated-domain benchmarks (medical,
  legal, financial) where every non-trivial implication needs a citation
  to a guideline, statute, or peer-reviewed source. `Reference` fields:
  `citation` (required), `doi`, `url`, `section`, `note`. Authors may
  pass a plain string anywhere a `Reference` is expected — it
  auto-promotes to `Reference(citation=s)` via a `mode="before"`
  validator, so `references: ["Ranieri et al. (2012)"]` and
  `references: [{"citation": "Ranieri et al. (2012)", "doi": "..."}]`
  both work. Nine new unit tests in `tests/unit/test_benchmark_io.py`
  cover the structured form, string shorthand at both item and bearer
  levels, backwards-compatibility (all-empty defaults on existing
  benchmarks), populated-everywhere round-tripping, and the `extra
  = forbid` regression boundary.

### Changed

- **Documentation**: `docs/authoring_benchmarks.md` adds a new "Step 7b:
  Add references" subsection with a worked example showing both
  shorthand and structured forms, and a brief justification covering
  auditability, reproducibility under analyst turnover, and downstream
  tooling.
- **Static schema**: `src/infereval/schemas/benchmark.schema.json`
  regenerated to include the new `$defs.Reference` and the optional
  `references` arrays at the three levels. `schema_version` stays
  `"1.0"` — adding optional fields with defaults is the textbook
  backwards-compatible additive change, and every pre-0.2.2 benchmark
  validates unchanged.

## [0.2.1] — 2026-05-19

Single-issue patch release. Restores correct evaluation behavior against
`claude-opus-4-7` (and any Anthropic model) under platform capacity strain.

### Fixed

- **Issue #16** — `AnthropicProvider._is_transient` now classifies HTTP
  503 (`ServiceUnavailableError`), 504 (`DeadlineExceededError`), and
  529 (`OverloadedError`) as transient, in addition to the previously
  recognised `RateLimitError` / `APIConnectionError` / `APITimeoutError`
  / `InternalServerError`. The corresponding SDK exception subclasses
  live under `anthropic._exceptions` and are not exported at the
  top-level namespace, so the fix matches by status code on the public
  `APIStatusError` base class. Without this fix, 529 storms during
  capacity events were recorded as `parse_status: sample_failed`,
  occluding the analyst's verdicts from κ_C / κ_F and depressing
  coverage. Observed in the wild on 2026-05-19: a 29-item
  pulmonary-edema benchmark against Opus 4.7 dropped to coverage
  0.7241 because 22 of 87 samples 529'd; the patched run on the same
  benchmark recovered to coverage 1.0000 in ~3 minutes wall time vs
  ~16 minutes for the failed-retry-chain version. Five new unit tests
  in `tests/unit/test_provider_anthropic.py` cover the new branch and
  guard the regression boundary (400 must remain non-transient).

## [0.2.0] — 2026-05-18

Methodology- and provider-level improvements surfaced during 0.1.0 use
against real APIs (the paraphrase-axis experiment and multi-model
triangulation). All v0.2.0 milestone issues closed.

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

### Changed

- **`VerificationPromptOverride` gains optional `system` and `id` fields.**
  A benchmark JSON can now fully specify a custom verification prompt
  (system + user template + parse regex + identifier) without dropping
  to the Python API. The paraphrase-axis experiment in
  `experiments/paraphrase_axis_triangulation.py` is now JSON-drivable.
  Closes #6.
- **Default `max_tokens` raised from 32 to 1024** on both
  `infereval.providers.base.SampleRequest` and
  `infereval.evaluation.ProviderParams`. The old default budget-clipped
  any reasoning-capable model. The new default is generous for non-
  reasoning models (which only emit a handful of tokens for a one-word
  verdict regardless of the cap) and sufficient for current reasoning
  models. Closes #4.
- **`SampleRecord` gains `finish_reason` and `reasoning_tokens`
  fields** (both `Optional[str]` / `Optional[int]`, defaulting to
  `None`). Providers populate them where available — OpenAI from
  `choices[0].finish_reason` and `usage.completion_tokens_details.reasoning_tokens`;
  Anthropic from `response.stop_reason` and `usage.thinking_tokens`. The
  fields round-trip through the evaluation JSON. Closes #5.
- **`ParseStatus` gains `"budget_clipped"`**. The endorser promotes
  `"unparseable"` to `"budget_clipped"` whenever the provider's
  `finish_reason` is in the canonical budget-hit set (OpenAI `"length"`,
  Anthropic `"max_tokens"`). Verdict still falls back to `abstain` per
  Definition 2, but the parse_status now tells the analyst the abstain
  is operational (raise `max_tokens` and re-run), not a model decision.
- **`ParseStatus`** is now a single canonical type in
  `infereval.types` rather than two divergent definitions in
  `prompts.py` and `evaluation.py`.

### Fixed

- **OpenAIProvider**: route to `max_completion_tokens` for GPT-5.x and
  the o-series (o1, o3, o4) reasoning models; keep legacy `max_tokens`
  for pre-5.x models. OpenAI deprecated `max_tokens` for these families
  as of mid-2026, and the framework was silently failing every call
  against them. Closes #9.
- **AnthropicProvider**: skip the `temperature` parameter for Claude
  Opus 4.7 and later (the API rejects it as deprecated). Sonnet and
  Haiku still pass it through unchanged. Closes #10.

### Authors

- Bradley P. Allen, University of Amsterdam.

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

[0.2.0]: https://github.com/bradleypallen/infereval/releases/tag/v0.2.0
[0.1.0]: https://github.com/bradleypallen/infereval/releases/tag/v0.1.0
