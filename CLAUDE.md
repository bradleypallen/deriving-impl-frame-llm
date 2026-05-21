# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository contents

Two coupled artifacts:

1. **`revised.tex`** — the source LaTeX paper: *Note on Simonelli's Stop Sign Dialogue: An Implication-Space Methodology for the Empirical Evaluation of LLM Inferential Mastery* (Bradley P. Allen, University of Amsterdam).
2. **`src/infereval/`** — Python package implementing the methodology specified in the paper. Distributed on PyPI as `infereval`. The paper is the spec; the package is the executable companion.

The repository was seeded from an Overleaf import. The Python package was added later.

**Documentation map** (`docs/`):

- `docs/README.md` — table of contents.
- `docs/concepts.md` — methodology mental model (pedagogical complement to `revised.tex` §3–4).
- `docs/authoring_benchmarks.md` — writing a `benchmark.json` for a new domain.
- `docs/interpreting_metrics.md` — reading κ_C / κ_F / κ_F\* output, by-tag and factor-effects decompositions, sensitivity-sweep verdicts.
- `docs/providers.md` — per-provider quirks (Anthropic seed ignore, DeepSeek silent reasoning tokens, etc.).
- `docs/construct_validity_workflow.md` — end-to-end practitioner's guide for producing reproducible mastery-claim evidence.
- `docs/closing_the_construct_validity_gap.md` — implementation-annotated R1–R21 coverage record; which release closed which requirement.
- `docs/tutorials/*.ipynb` — four runnable Jupyter notebooks (quickstart, authoring, paraphrase-axis, pulmonology visualization). All run without API keys via the bundled `ReplayProvider` fixture.

## Build & run

### Paper

```
latexmk -pdf revised.tex
# or
pdflatex revised.tex && pdflatex revised.tex
```

Two passes when references change. Bibliography is inline (`thebibliography`); no `bibtex`/`biber`.

### Package

Editable install with dev tools:

```
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional extras:

- `[anthropic]` — Anthropic SDK
- `[openai]` — OpenAI SDK (also covers OpenRouter — OpenAI-API-compatible)
- `[stats]` — `statsmodels` for `infereval model` (factor-effects logistic regression, added in v0.4.1)
- `[all]` — union of the three above
- `[dev]` — extras above + pytest, pytest-cov, ruff, mypy, build, twine

Run tests:

```
pytest
```

CLI sanity check:

```
infereval --version
```

Live-provider tests (opt-in) require `RUN_LIVE_PROVIDER_TESTS=1` and the relevant API key in env.

## Paper structure and conventions

- **Document class:** `article`, 11pt, 1in margins. Loaded packages: `amsmath`, `amssymb`, `amsthm`, `mathtools`, `booktabs`, `array`, `tabularx`, `url`. There is no `hyperref` — URLs via `\url{}`. Do not add `hyperref` casually; ask first if links are needed.
- **Theorem environments:** `definition`, `remark`, `example`. Don't introduce `theorem`/`lemma`/`proposition` without a reason — the earlier "classical core" proposition has been demoted to a commented-out remark.
- **Citations:** Hlobil & Brandom (2025) `\cite{hlobil2025}` is central; Simonelli (2026) `\cite{simonelli2026}` is the dialogue being formalized. Other cites: `allen2025nesy`, `allen2026bbl`, `bang2025`, `wei2024`, `el-yaniv2010`. The paper relies on Hlobil–Brandom machinery (implication frames, Containment, RSR, NMMS, ≈, implicational roles, conceptual content, Corollary 77) and cites it *without restating definitions*. Don't inline Hlobil–Brandom definitions unless asked.
- **Notation invariants — keep stable across paper and code:**
  - $B$ — bearer set; $V$ vocabulary, $L = V^*$ token sequences
  - $\langle B, I \rangle$ / $\langle B, I_M \rangle$ — implication frame / derived from $M$
  - $\delta : B \to L$ — analyst-supplied expression function
  - $\mathrm{ctx}_\Gamma, \mathrm{ctx}_\Delta : \wp(B) \to L$ — analyst-supplied context construction
  - $E_M(\langle\Gamma,\Delta\rangle) \in \{\text{good}, \text{bad}, \text{abstain}\}$ — endorsement verdict
  - $\beta$ — benchmark; $\eta$ — evaluation; $V_i = (v_{i,1},\ldots,v_{i,m})$ — analyst verdict tuple; $c_i$ — analyst consensus
  - $\mathrm{cov}, \mathrm{cov}_j$ — coverage; $S$ — substantive index
  - $\kappa_C$ — Cohen's kappa; $\kappa_F$ — Fleiss' kappa with $M$ as $(m+1)$th annotator; $\kappa_F^*$ — inter-analyst Fleiss baseline
  - $\mathrm{RSR}$ — range of subjunctive robustness
  - **analyst** = human labeler; **annotator** = human-plus-$M$ ensemble. Load-bearing in the Fleiss definition — preserve it in code and prose.
- **Core claim:** $\langle B, I_M \rangle$ obeys Containment by construction via clause (i) of Definition 3. Stated as a remark, not a proposition. Edits to Definition 3 must preserve clause (i).
- **Commented-out material:** several remarks are present but commented out (deflationary "operational character", longer "structural character", classical-core invoking Corollary 77 + NMMS). Held back, not deleted. Do not uncomment without asking, and preserve the commented blocks when editing surrounding prose.
- **Trajectory:** formalization of Simonelli's stop-sign dialogue → general inferentialist evaluation methodology (binary classification with abstention, scored by coverage + Cohen's/Fleiss' kappa) → Discussion surfacing carving-relativity of content-attribution, evaluative vs. generative behavior, two axes of variation, and the carving-indexed form of in-principle claims. Preserve this arc when restructuring.

## Python package conventions

- **Package layout:** `src/infereval/` (src-layout). Top-level modules:
  - **Core (0.1.0):** `types`, `frame`, `benchmark`, `evaluation`, `endorsement`, `context`, `prompts`, `metrics`, `logging_setup`, `providers/`, `schemas/`, `cli/`.
  - **Construct-validity analytical extensions (0.4.x):** `structure` (Phase 2.1, R13), `modeling` (Phase 2.2, R10), `sweep` (Phase 2.3, R11), `report` (Phase 3, R16–R21).
  - **CLI subcommands** in `cli/`: `validate_cmd`, `describe_cmd`, `evaluate_cmd`, `metrics_cmd`, `structure_cmd` (0.4.0), `model_cmd` (0.4.1), `sweep_cmd` (0.4.2), `report_cmd` (0.5.0).
- **Code names track paper symbols:** `Verdict` enum (`GOOD`/`BAD`/`ABSTAIN`), `Bearer`, `Implication`, `DerivedFrame`, `Benchmark`/`Evaluation` (Pydantic for JSON I/O), `Endorser` (computes $E_M$), `cohens_kappa`, `fleiss_kappa`, `inter_analyst_fleiss`. The analyst/annotator distinction lives in `fleiss_kappa` (annotators = m + 1) vs `inter_analyst_fleiss` (analysts = m). Construct-validity additions: `Panel`, `inter_analyst_fleiss_per_panel`, `cross_panel_kappa` (0.3.3), `FactorEffect` / `ModelFit` (0.4.1), `SweepResult` with `stability_verdict` (0.4.2), `StructureReport` (0.4.0), `ConstructValidityClaims` / `ReportVerdict` (0.5.0), `collect_negative_findings` (0.5.1).
- **Build:** `hatchling`. Single-source version at `src/infereval/__init__.py:__version__`.
- **Python:** `>=3.10`. Strict mypy. `statsmodels` / `pandas` imports require `# type: ignore[import-untyped]`.
- **Lint:** `ruff` (E, F, I, B, UP, N, SIM; line-length 100). Statistical conventions that violate ruff N (e.g. `X` for a design matrix) get an inline `# noqa: N806 -- statistical convention` comment.

## Locked methodology defaults (settled in conversation)

These are framework defaults, overridable per evaluation:

- **Package name:** `infereval` (PyPI distribution + import).
- **License:** MIT.
- **Verification prompt:** fresh `default-v1` template (GOOD/BAD/ABSTAIN tokens with brief glosses). Follows `allen2025nesy` methodology but is not a literal quote.
- **`n_samples`:** 5 (odd, clean 3-way majority).
- **`max_tokens`:** 1024 at both the Python API (`ProviderParams.max_tokens`) and the CLI (`--max-tokens`). Aligned in v0.5.2 — earlier CLI default of 32 was a holdover that silently budget-clipped reasoning models. Bump to 2048–4096 for `o1-pro` / `o3-pro` / `qwen3-max-thinking` and other heavy-reasoning variants.
- **Verdict-audit caps (v0.5.3):** `compute_verdict` is *not* a function of the claims file alone — it consults the structure report and the benchmark. Two audit rules cap the verdict at `partially_defensible`: any structural anomaly in a check marked `_run=True` ("ran but did not pass"), and `m < 2` analysts at `items_in_benchmark` scope ("no inter-analyst baseline to certify against"). Future analytical checks that produce artifacts should follow the same pattern: thread the artifact into `compute_verdict` and cap when the artifact reveals the check didn't pass.
- **Tie-break:** `abstain` (matches paper's treatment of abstain as safe fallback). Configurable: `abstain` / `good` / `bad` / `first`.
- **$\delta$ / $\mathrm{ctx}_\Gamma$ / $\mathrm{ctx}_\Delta$ placement:** both JSON template form (default) and Python plugin form (escape hatch).
- **TeX in `expression` strings:** **strip TeX-math `$...$` delimiters at prompt construction time.** Expressions stay LaTeX-source-friendly in benchmark JSON; prompts see the de-TeX'd form.
- **Concurrency:** sequential by default; no `--workers` flag ships yet. Async / batched provider calls and bootstrap CIs on metrics remain unshipped — both are tracked but not yet scheduled.
- **Cohen's kappa default reference:** consensus $c_i$. Override with `--reference analyst:<id>`.
- **Logging:** stdlib `logging` + JSONL formatter (zero-dep, grep/jq friendly).
- **OpenAI SDK surface:** Chat Completions (max OpenRouter coverage).
- **OpenRouter:** thin subclass of `OpenAIProvider` overriding `base_url`.
- **$\kappa_F^*$ in CLI output:** always shown ("undefined" per paper's Remark 5 when $m<2$ or unanimous).
- **Schema versioning:** independent of framework (`schema_version: "1.0"`). Schema stability promised from 1.0 onward, not 0.x. **The 0.3.x–0.5.x construct-validity series added optional fields only** — every pre-0.3.0 benchmark continues to validate against the current schema, and that additive-only invariant must be preserved for further benchmark-schema changes within the 1.0 line.
- **`DerivedFrame` materialization:** lazy (membership via Def. 3 iff). Full $I_M$ over $\wp(B)\times\wp(B)$ is unbounded.

## Construct-validity infrastructure (v0.3.0–v0.5.4)

The nine-feature programme shipped over eleven patch/minor releases addresses the R1–R21 requirements catalogued in [`docs/closing_the_construct_validity_gap.md`](docs/closing_the_construct_validity_gap.md). Practitioner walk-through is in [`docs/construct_validity_workflow.md`](docs/construct_validity_workflow.md). Quick map for future work:

**Optional benchmark schema fields added (all additive):**

| Field | Release | What it enables |
|---|---|---|
| `factors`, `factor_constraints` (benchmark-level) + `factor_levels` (per item) | 0.3.0 | Crossed factorial design with `min_items_per_cell` validation; consumed by `infereval model`. |
| `paraphrases` runtime activation via `--paraphrase-variant K` / `--paraphrase-cycle` | 0.3.1 | Paraphrase-axis robustness becomes a one-flag operation. `paraphrases` field was already permitted in 0.1.0 but ignored at runtime. |
| `construction_metadata` per item (`authored_by`, `authored_on`, `authored_blind_to_models`, `source`) | 0.3.2 | Item-level provenance for held-out / training-data-separation arguments. |
| `analyst.panel` + `benchmark.primary_panel` | 0.3.3 | Reference-panel declaration for cross-panel convergent-validity checks; validator enforces all-or-none on the `panel` field. |
| `factor_kinds` (benchmark-level) | 0.5.3 | Per-factor valence label (`"substantive"` vs `"experimentally_controlled"`). Used by `collect_negative_findings` to render null Wald-test findings with the correct valence — substantive nulls weaken the claim, controlled nulls strengthen it. |
| `analyst_rationales` (per item) | 0.5.4 | Optional `list[str] \| None` of natural-language rationales positionally aligned to `analyst_verdicts`. Propagated through `EvaluationItem` (and therefore covered by `benchmark_hash`). `None` ≠ empty-string entry. The substrate for the deferred disagreement-diagnosis workstream. Metric / structural-check outputs are byte-identical with and without rationales (AR2 regression test). |

**New analytical CLI commands (all consume `eta.json` + `benchmark.json` and feed `infereval report`):**

| Command | Release | What it does |
|---|---|---|
| `infereval structure` | 0.4.0 | Three deterministic checks on the benchmark — Containment, RSR role consistency, base-case stability. Content-validity gate. |
| `infereval model` | 0.4.1 | Logistic regression of per-sample agreement on declared `factors`, item-clustered SEs, per-factor joint Wald tests + per-level coefficients. Requires `[stats]`. |
| `infereval sweep` | 0.4.2 | Re-runs `metrics` across a swept parameter (e.g. `--vary tie_break --values abstain,good,bad`); emits a stability verdict based on κ_C range (`<0.05` stable, `<0.10` moderately sensitive, `≥0.10` substantively variable). |
| `infereval report` | 0.5.0 | Combines claims file + the four analytical outputs into a Markdown report with a deterministic five-tier verdict. Auto-collects negative findings (0.5.1); `--suppress-negatives` downgrades the verdict one tier. v0.5.3 added verdict audit caps (structural anomalies and m<2 cap the verdict at `partially_defensible`) and `factor_kinds` valence labels on negative findings. |

**Notes for future work in this area:**

- The "all four analytical commands feed `report`" pattern is load-bearing — when adding new analytical capabilities, prefer extending one of the existing four or wiring a new one into `collect_negative_findings()` / the report renderer over standing up a sibling CLI surface.
- Construct-validity is **constitutively partial**. Requirements that the source document calls *irreducibly outside the framework* (independent analyst panels, held-out item construction with bona-fide blinding, training-data temporal separation, cross-domain replication, the in-principle interpretive commitments) cannot be moved inside it. The framework can declare and check that an analyst made these commitments; it cannot vet them.
- The deterministic verdict in `report` is a function of declared claims plus measured evidence — never a free-text summary. Any change to the verdict logic must be specified in `compute_verdict()` and tested.

## Working style for this repo

- Paper edits go to `revised.tex` via `Edit` (not `Write`) unless rewriting wholesale. After non-trivial paper changes, run `latexmk -pdf revised.tex` to confirm it compiles.
- Code edits go in `src/infereval/`. Run `pytest` after changes; type-check with `mypy src/infereval/`. The full test suite is ~592 tests and finishes in under 5 seconds.
- The methodology defaults above are locked in conversation. Don't drift from them without checking with the user first.
- Per user-global instruction: **always include structured logging for post-experimental run analysis and reporting.** Every model call, every sample, every majority-vote outcome should be auditable from the JSONL log.
- **Schemas are generated, not hand-edited.** After any change to the Pydantic models in `benchmark.py` or `evaluation.py`, regenerate the committed Draft 2020-12 schemas with `python -c "from infereval.schemas import emit_static_schemas; emit_static_schemas()"`. A drift test keeps these in sync; CI will flag a hand-edit. Version bumps also flow into `evaluation.schema.json:framework_version.default` via the same regeneration step.
- **Release flow** (matches v0.3.0–v0.5.4): bump `src/infereval/__init__.py:__version__`, update `CHANGELOG.md` (Keep-a-Changelog format), regenerate schemas, open + rebase-merge a PR, then tag (`git tag -a vX.Y.Z <merge-sha> -m "..."` and `git push origin vX.Y.Z`), then `python -m build` and `gh release create vX.Y.Z dist/*.whl dist/*.tar.gz --title "..." --notes "..."`. PyPI upload is a manual `twine upload` step — there is no GitHub Actions workflow.
- **PR merge style**: rebase-merge via `gh api -X PUT repos/<owner>/<repo>/pulls/<num>/merge -f merge_method=rebase`. Worktree-safe (doesn't require switching the local HEAD).
- **macOS UF_HIDDEN gotcha**: if an editable install seems to disappear from `.venv`, run `chflags -R nohidden .venv` before pytest. Documented in the user's `MEMORY.md`.
