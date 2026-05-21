# Documentation

The README is the front door. This directory has the longer-form material.

## Guides

| Guide | When you want it |
|---|---|
| [**Concepts**](concepts.md) | Mental model of the methodology — bearers, expression functions, contexts, the endorsement function `E_M`, the derived frame, the benchmark, the metrics. Pedagogical complement to the paper, §3–4. |
| [**Authoring benchmarks**](authoring_benchmarks.md) | Writing your own `benchmark.json` for a new domain — bearer carving, expression functions, RSR targets, factorial design, construction provenance, reference panels, validation. |
| [**Interpreting metrics**](interpreting_metrics.md) | What κ_C, κ_F, κ_F\* (per-panel and cross-panel) tell you; reading by-tag and factor-effects decompositions; sensitivity-sweep stability verdicts; what to do about low coverage. |
| [**Providers**](providers.md) | Per-provider quirks: Anthropic's seed ignore, DeepSeek's silent reasoning tokens, OpenRouter attribution headers, the OpenAI Chat-Completions choice. |
| [**Construct-validity workflow**](construct_validity_workflow.md) | End-to-end practitioner's guide for producing reproducible, well-founded evidence for a claim of inferential mastery against a carving. Covers the framework's nine analytical capabilities plus the research-program responsibilities that remain outside the tool. |
| [**Closing the construct-validity gap**](closing_the_construct_validity_gap.md) | Implementation-annotated companion to the workflow guide — which requirements (R1–R21) each release closed, what remains research-program work, and the as-shipped coverage table. |

## Tutorials (Jupyter notebooks)

Each tutorial runs end-to-end without any API key by using the bundled `ReplayProvider` fixture or `ScriptedProvider`. To replace replay/scripted with a real provider, set the appropriate API key env var (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `OPENROUTER_API_KEY`) and swap the provider construction call.

| Tutorial | Topic |
|---|---|
| [`01_quickstart.ipynb`](tutorials/01_quickstart.ipynb) | The README quickstart, interactively — describe → validate → evaluate → metrics, against the committed stop-sign replay fixture. |
| [`02_authoring_a_benchmark.ipynb`](tutorials/02_authoring_a_benchmark.ipynb) | Build a small medical-defeasibility benchmark from scratch. Carve bearers, write expressions, declare items, validate, evaluate against the replay provider. |
| [`03_paraphrase_axis_experiment.ipynb`](tutorials/03_paraphrase_axis_experiment.ipynb) | Narrate the cross-model paraphrase-axis experiment from `experiments/paraphrase_axis_triangulation.py`, with explanations between the cells that produce the cross-model κ_C table. |
| [`04_pulmonology_visualization.ipynb`](tutorials/04_pulmonology_visualization.ipynb) | Visual analytics on the bundled pulmonary-edema benchmark + the six cross-family evaluations: bearer co-occurrence heatmap, per-target verdict distribution, item × model verdict matrix, pairwise Cohen κ, per-item disagreement counts. Requires `matplotlib` + `pandas`. |

## Reference

- **API reference**: the docstrings in `src/infereval/*.py` are kept comprehensive and paper-cross-referenced. `help(infereval.evaluation.evaluate)` is reliable.
- **CLI commands** (each has `--help`): `validate`, `describe`, `evaluate`, `metrics`, **`structure`** (v0.4.0), **`model`** (v0.4.1), **`sweep`** (v0.4.2), **`report`** (v0.5.0).
- **JSON Schemas** (Draft 2020-12): committed at [`src/infereval/schemas/benchmark.schema.json`](../src/infereval/schemas/benchmark.schema.json) and [`evaluation.schema.json`](../src/infereval/schemas/evaluation.schema.json). They are generated from the Pydantic models; a drift test keeps them in sync.
- **Paper**: the methodology's normative specification, *Note on Simonelli's Stop Sign Dialogue* (Allen 2026), is maintained as a separate paper. These docs are the gentle introduction.

## Stability

- **Framework version**: 0.x — public Python API may shift between minor releases. Stable from 1.0.
- **JSON schemas** (`schema_version: "1.0"`): versioned independently from the framework. **Stability from 1.0 onward is promised** regardless of framework version. The construct-validity infrastructure series (v0.3.0 → v0.5.1) added optional fields only — every pre-0.3.0 benchmark continues to validate against the current schema.
- **CLI surface**: subcommand and flag names track the framework version. Stable from 1.0.

See [`CHANGELOG.md`](../CHANGELOG.md) at the repo root for per-release notes.
