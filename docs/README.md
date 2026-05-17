# Documentation

The README is the front door. This directory has the longer-form material.

## Guides

| Guide | When you want it |
|---|---|
| [**Concepts**](concepts.md) | Mental model of the methodology — bearers, expression functions, contexts, the endorsement function `E_M`, the derived frame, the benchmark, the metrics. Pedagogical complement to revised.tex §3–4. |
| [**Authoring benchmarks**](authoring_benchmarks.md) | Writing your own `benchmark.json` for a new domain — bearer carving, expression functions, RSR targets, validation. |
| [**Interpreting metrics**](interpreting_metrics.md) | What κ_C, κ_F, and κ_F\* tell you; reading by-tag decompositions; what to do about low coverage. |
| [**Providers**](providers.md) | Per-provider quirks: Anthropic's seed ignore, DeepSeek's silent reasoning tokens, OpenRouter attribution headers, the OpenAI Chat-Completions choice. |

## Tutorials (Jupyter notebooks)

Each tutorial runs end-to-end without any API key by using the bundled `ReplayProvider` fixture. To replace replay with a real provider, set the appropriate API key env var (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `OPENROUTER_API_KEY`) and swap the `get_provider("replay", ...)` call.

| Tutorial | Topic |
|---|---|
| [`01_quickstart.ipynb`](tutorials/01_quickstart.ipynb) | The README quickstart, interactively — describe → validate → evaluate → metrics, against the committed stop-sign replay fixture. |
| [`02_authoring_a_benchmark.ipynb`](tutorials/02_authoring_a_benchmark.ipynb) | Build a small medical-defeasibility benchmark from scratch. Carve bearers, write expressions, declare items, validate, evaluate against the replay provider. |
| [`03_paraphrase_axis_experiment.ipynb`](tutorials/03_paraphrase_axis_experiment.ipynb) | Narrate the cross-model paraphrase-axis experiment from `experiments/paraphrase_axis_triangulation.py`, with explanations between the cells that produce the cross-model κ_C table. |

## Reference

- **API reference**: the docstrings in `src/infereval/*.py` are kept comprehensive and paper-cross-referenced. `help(infereval.evaluation.evaluate)` is reliable. A rendered docs site (MkDocs Material) is on the 0.2.0 roadmap.
- **JSON Schemas** (Draft 2020-12): committed at [`src/infereval/schemas/benchmark.schema.json`](../src/infereval/schemas/benchmark.schema.json) and [`evaluation.schema.json`](../src/infereval/schemas/evaluation.schema.json). They are generated from the Pydantic models; a drift test keeps them in sync.
- **CLI help**: `infereval --help`, `infereval evaluate --help`, etc.
- **Paper**: [`revised.tex`](../revised.tex) is the methodology's normative specification. These docs are the gentle introduction.

## Stability

- **Framework version**: 0.x — public Python API may shift between minor releases. Stable from 1.0.
- **JSON schemas** (`schema_version: "1.0"`): versioned independently from the framework. **Stability from 1.0 onward is promised** regardless of framework version.
- **CLI surface**: subcommand and flag names track the framework version. Stable from 1.0.

See [`CHANGELOG.md`](../CHANGELOG.md) at the repo root for per-release notes.
