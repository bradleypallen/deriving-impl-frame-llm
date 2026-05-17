# Authoring benchmarks

This guide walks through writing a `benchmark.json` for your own domain. We'll do a small medical-defeasibility example end-to-end, then point you at the validation tools.

If you'd rather build it interactively, the same content is in [`tutorials/02_authoring_a_benchmark.ipynb`](tutorials/02_authoring_a_benchmark.ipynb).

## The skeleton

A benchmark file has five top-level pieces, plus an `id` and optional descriptive metadata:

```json
{
  "schema_version": "1.0",
  "id": "<your-benchmark-id>",
  "title": "...",
  "domain": "...",
  "description": "...",

  "bearers":    {...},        // map from bearer id → expression
  "analysts":   [...],        // who labeled this
  "context_builders": {...},  // how to package premise / conclusion sets
  "items":      [...]         // the implications + analyst verdicts
}
```

A `verification_prompt` override field exists but most benchmarks should leave it alone (the framework default is the locked `default-v1` template).

## Step 1: Decide what you're measuring

Before writing JSON, write down (on paper or in a comment):

1. **The domain.** "Medical reasoning about treatment selection." "Contract enforceability." "Default reasoning about animals."
2. **The inferential structure you care about.** Pick one or a few **target inferences** — the inferences whose RSR (range of subjunctive robustness) you want to characterize. For our medical example: `bacterial diagnosis ⟹ antibiotics indicated`.
3. **The defeaters and irrelevant additions** for those target inferences. What are the side-premises that would change the verdict? What are the ones that shouldn't?

These three things tell you what bearers you need.

## Step 2: Carve the bearers

For our medical example, the target inference is `bd ⟹ ab` (`a has a bacterial diagnosis` ⟹ `antibiotics are indicated for a`). The natural side-premises to test:

- `sf` — `a has a fever` (irrelevant addition: doesn't change the conclusion)
- `cf` — `a has a cough` (irrelevant addition)
- `vd` — `a has a viral co-infection` (defeater: antibiotics still indicated for the bacterial part, so this is actually irrelevant — but worth testing)
- `pa` — `a is allergic to penicillin` (defeater: changes which antibiotic, but "antibiotics indicated" still holds — also a subtle case)
- `pcr` — `a's bacterial diagnosis was a PCR false positive` (definitive defeater)
- `re` — `a has fully recovered` (definitive defeater)

The carving is a judgment call. There is no "correct" set; you pick what captures the inferential structure your analysis cares about.

Be honest about ambiguity. If `δ(pa) = "a is allergic to penicillin"` could plausibly trigger either "still need antibiotics, just a different class" or "no antibiotics" depending on how the model carves the predicates, the benchmark item using `pa` is going to be hard to interpret — and that's *good*, because it surfaces a real ambiguity in the domain.

## Step 3: Write the bearers section

```json
"bearers": {
  "bd":  {"expression": "a has a bacterial diagnosis"},
  "ab":  {"expression": "antibiotics are indicated for a"},
  "sf":  {"expression": "a has a fever"},
  "cf":  {"expression": "a has a cough"},
  "vd":  {"expression": "a has a viral co-infection"},
  "pcr": {"expression": "a's bacterial diagnosis was a PCR false positive"},
  "re":  {"expression": "a has fully recovered"}
}
```

The bearer id (`bd`, `ab`, ...) is what travels through implications. The `expression` is what the model sees (via `δ`) after TeX-math delimiters are stripped at prompt time.

If you have multiple natural phrasings of the same bearer, list them in `paraphrases`:

```json
"bd": {
  "expression": "a has a bacterial diagnosis",
  "paraphrases": [
    "a's diagnosis indicates a bacterial infection",
    "a has been diagnosed with a bacterial illness"
  ]
}
```

The paraphrases are unused by `default-v1` runs (a future release will let you cycle through them for paraphrase-axis experiments without authoring multiple benchmarks). For now, including them is documentation.

## Step 4: Declare the analyst panel

```json
"analysts": [
  {"id": "physician-a", "display_name": "Dr. A (internal medicine)",
   "notes": "Labels reflect the analyst's reading of current clinical practice."},
  {"id": "physician-b", "display_name": "Dr. B (infectious disease)"}
]
```

`m = len(analysts)` is the number of analysts. Each item's `analyst_verdicts` list must have exactly `m` entries, in the same order as the `analysts` array.

The number of analysts matters: `κ_F*(β)`, the inter-analyst baseline, is only defined when `m ≥ 2` and the analysts are not unanimous on every item. With `m = 1` (like our stop-sign example) you have a benchmark but no baseline.

## Step 5: Declare context builders (usually leave default)

```json
"context_builders": {
  "premise":    {"kind": "template", "template": "{expressions}", "joiner": " and "},
  "conclusion": {"kind": "template", "template": "{expressions}", "joiner": " or "}
}
```

This is the default and matches Simonelli's dialogue. Skip the field entirely to use it implicitly. Override only if you need richer construction (e.g. "Granting normal background conditions, ..." as a wrapper template), which is rarely the right move — paraphrase the bearers directly instead.

## Step 6: Write the items

Each item declares one `⟨Γ, Δ⟩` implication plus one verdict per analyst:

```json
"items": [
  {
    "id": "base",
    "premises":    ["bd"],
    "conclusions": ["ab"],
    "analyst_verdicts": ["good", "good"],
    "tags": ["base-inference"],
    "rsr_target": {"X": ["bd"], "A": ["ab"]}
  },
  {
    "id": "irrelevant-fever",
    "premises":    ["bd", "sf"],
    "conclusions": ["ab"],
    "analyst_verdicts": ["good", "good"],
    "tags": ["irrelevant-addition", "symptom"],
    "rsr_target": {"X": ["bd"], "A": ["ab"]}
  },
  {
    "id": "defeater-pcr",
    "premises":    ["bd", "pcr"],
    "conclusions": ["ab"],
    "analyst_verdicts": ["bad", "bad"],
    "tags": ["defeater", "false-positive"],
    "rsr_target": {"X": ["bd"], "A": ["ab"]}
  },
  {
    "id": "defeater-recovered",
    "premises":    ["bd", "re"],
    "conclusions": ["ab"],
    "analyst_verdicts": ["bad", "bad"],
    "tags": ["defeater", "recovered"],
    "rsr_target": {"X": ["bd"], "A": ["ab"]}
  },
  {
    "id": "ambiguous-coinfection",
    "premises":    ["bd", "vd"],
    "conclusions": ["ab"],
    "analyst_verdicts": ["good", "good"],
    "tags": ["irrelevant-addition", "coinfection"],
    "rsr_target": {"X": ["bd"], "A": ["ab"]}
  }
]
```

What each field does:

- **`id`**: unique within the benchmark. Used for log lookups and decompositions.
- **`premises` / `conclusions`**: lists of bearer ids. Order doesn't matter (the model treats them as sets); the framework sorts and dedupes them on input.
- **`analyst_verdicts`**: `m`-tuple of `"good" | "bad" | "abstain"`. Order matches the `analysts` array.
- **`tags`**: arbitrary labels for `by-tag` decomposition. `infereval metrics --by-tag <tag>` filters to items carrying that tag. Common conventions: `base-inference`, `irrelevant-addition`, `defeater`, plus domain-specific descriptors.
- **`rsr_target`** (optional): the target inference `⟨X, A⟩` this item helps characterize the RSR of. Items with the same `rsr_target` form a coherent subset for `infereval metrics --by-rsr-target`. Use it whenever you have multiple items probing the same target.

## Step 7: Validate

```
infereval validate path/to/your-benchmark.json
```

The validator runs the full Pydantic checks: every bearer id referenced in `premises` / `conclusions` / `rsr_target` exists in `bearers`; every item has exactly `m` analyst verdicts; analyst and item ids are unique; verdict values are in `{good, bad, abstain}`; etc. The error messages name the offending field and value.

For non-Python downstream consumers, the same checks (modulo cross-field ones) live in the committed JSON Schema at [`src/infereval/schemas/benchmark.schema.json`](../src/infereval/schemas/benchmark.schema.json).

## Step 8: Describe

```
infereval describe path/to/your-benchmark.json
```

Prints the bearer count, item count, analyst panel, per-analyst label distribution, `κ_F*` baseline (when `m ≥ 2` and the analysts are non-unanimous), tag frequencies, and RSR-target groupings. This is your sanity check — does the benchmark look like what you intended?

## Step 9: Smoke-test with the mock provider

Before spending API calls, check the framework wiring with `--replay-from` (if you have a fixture) or with a `ScriptedProvider` via the Python API:

```python
from infereval.benchmark import Benchmark
from infereval.evaluation import EndorsementConfig, evaluate
from infereval.providers.mock import ScriptedProvider

bench = Benchmark.load("path/to/your-benchmark.json")
# 5 items × 5 samples = need 25 responses
provider = ScriptedProvider(responses=["GOOD"] * 15 + ["BAD"] * 10)
eta = evaluate(bench, provider, config=EndorsementConfig(n_samples=5))
print(f"items={eta.n}")
print(f"first item samples: {[s.raw_response for s in eta.items[0].samples]}")
```

Good outcomes here:
- No exceptions during construction or evaluation.
- The shape of `eta` matches what you expect.
- All items got `len(samples) == n_samples`.

## Step 10: Run it for real

```
export ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY / OPENROUTER_API_KEY
infereval evaluate path/to/your-benchmark.json \
    --provider anthropic --model claude-haiku-4-5-20251001 \
    --output medical-eta.json \
    --n-samples 5 --max-tokens 512 \
    --log medical-run.jsonl
```

Note: explicitly pass `--max-tokens 512` if you're hitting any reasoning-capable model. The framework default of 32 is too low for DeepSeek-style models that use silent reasoning tokens. See [`providers.md`](providers.md) for the per-provider list.

Then:

```
infereval metrics medical-eta.json --benchmark path/to/your-benchmark.json
infereval metrics medical-eta.json --benchmark path/to/your-benchmark.json \
    --by-tag irrelevant-addition --by-tag defeater
```

[`interpreting_metrics.md`](interpreting_metrics.md) walks through what to do with the output.

## Common pitfalls

**Carving too fine or too coarse.** If your bearers are too fine-grained, your items become combinatorial (and your analysts have to label many of them). If too coarse, the inferential structure you wanted to probe gets washed out. Aim for a bearer set that supports 4–20 items per target inference.

**Implicit assumptions in `δ`.** "`a is allergic to penicillin`" embeds the assumption that "antibiotics" generically includes penicillin. If the model disambiguates ("we'd use a non-penicillin antibiotic"), it's reading `ab` differently than your analysts. The fix is to make `δ(ab)` precise about which assumption you're testing.

**Disagreement between analysts you didn't expect.** This is *good information* — it means the domain has genuine ambiguity that the methodology will surface as `κ_F*(β) < 1`. Don't paper over it by forcing unanimous labels. The methodology lets you say "this benchmark has inter-analyst κ_F* = 0.67; the model achieves κ_C = 0.55 against consensus", which is a useful and honest statement.

**Forgetting to set `--max-tokens`.** Symptom: high abstain rate, low coverage. Cause: budget-clipping. Fix: `--max-tokens 256` or higher.

## Where to go next

- Run a real evaluation: [`providers.md`](providers.md).
- Read the output: [`interpreting_metrics.md`](interpreting_metrics.md).
- See the conceptual framework that makes all this coherent: [`concepts.md`](concepts.md) and `revised.tex`.
