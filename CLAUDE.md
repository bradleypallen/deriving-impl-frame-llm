# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository contents

Two coupled artifacts:

1. **`revised.tex`** — the source LaTeX paper: *Note on Simonelli's Stop Sign Dialogue: An Implication-Space Methodology for the Empirical Evaluation of LLM Inferential Mastery* (Bradley P. Allen, University of Amsterdam).
2. **`src/infereval/`** — Python package implementing the methodology specified in the paper. Distributed on PyPI as `infereval`. The paper is the spec; the package is the executable companion.

The repository was seeded from an Overleaf import. The Python package was added later.

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

Optional provider extras: `[anthropic]`, `[openai]` (also covers OpenRouter — OpenAI-API-compatible), `[all]`.

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

- **Package layout:** `src/infereval/` (src-layout). Modules: `types`, `frame`, `benchmark`, `evaluation`, `endorsement`, `context`, `prompts`, `metrics`, `logging_setup`, `providers/`, `schemas/`, `cli/`. Most are stubs in M0; populated through M1–M7.
- **Code names track paper symbols:** `Verdict` enum (`GOOD`/`BAD`/`ABSTAIN`), `Bearer`, `Implication`, `DerivedFrame`, `Benchmark`/`Evaluation` (Pydantic for JSON I/O), `Endorser` (computes $E_M$), `cohens_kappa`, `fleiss_kappa`, `inter_analyst_fleiss`. The analyst/annotator distinction lives in `fleiss_kappa` (annotators = m + 1) vs `inter_analyst_fleiss` (analysts = m).
- **Build:** `hatchling`. Single-source version at `src/infereval/__init__.py:__version__`.
- **Python:** `>=3.10`. Strict mypy.
- **Lint:** `ruff` (E, F, I, B, UP, N, SIM; line-length 100).

## Locked methodology defaults (settled in conversation)

These are framework defaults, overridable per evaluation:

- **Package name:** `infereval` (PyPI distribution + import).
- **License:** MIT.
- **Verification prompt:** fresh `default-v1` template (GOOD/BAD/ABSTAIN tokens with brief glosses). Follows `allen2025nesy` methodology but is not a literal quote.
- **`n_samples`:** 5 (odd, clean 3-way majority).
- **Tie-break:** `abstain` (matches paper's treatment of abstain as safe fallback). Configurable: `abstain` / `good` / `bad` / `first`.
- **$\delta$ / $\mathrm{ctx}_\Gamma$ / $\mathrm{ctx}_\Delta$ placement:** both JSON template form (default) and Python plugin form (escape hatch).
- **TeX in `expression` strings:** **strip TeX-math `$...$` delimiters at prompt construction time.** Expressions stay LaTeX-source-friendly in benchmark JSON; prompts see the de-TeX'd form.
- **Async / batched provider calls:** deferred to 0.2.0. 0.1.0 is sequential by default; threaded concurrency via `--workers` is allowed in M7 with reproducibility caveats.
- **Cohen's kappa default reference:** consensus $c_i$. Override with `--reference analyst:<id>`.
- **Bootstrap CIs on metrics:** deferred to 0.2.0.
- **Logging:** stdlib `logging` + JSONL formatter (zero-dep, grep/jq friendly).
- **OpenAI SDK surface:** Chat Completions (max OpenRouter coverage).
- **OpenRouter:** thin subclass of `OpenAIProvider` overriding `base_url`.
- **$\kappa_F^*$ in CLI output:** always shown ("undefined" per paper's Remark 5 when $m<2$ or unanimous).
- **Schema versioning:** independent of framework (`schema_version: "1.0"`). Schema stability promised from 1.0 onward, not 0.x.
- **`DerivedFrame` materialization:** lazy (membership via Def. 3 iff). Full $I_M$ over $\wp(B)\times\wp(B)$ is unbounded.

## Working style for this repo

- Paper edits go to `revised.tex` via `Edit` (not `Write`) unless rewriting wholesale. After non-trivial paper changes, run `latexmk -pdf revised.tex` to confirm it compiles.
- Code edits go in `src/infereval/`. Run `pytest` after changes; type-check with `mypy src/infereval/`.
- The methodology defaults above are locked in conversation. Don't drift from them without checking with the user first.
- Per user-global instruction: **always include structured logging for post-experimental run analysis and reporting.** Every model call, every sample, every majority-vote outcome should be auditable from the JSONL log.
