# Interpreting metrics

You ran `infereval evaluate`, you ran `infereval metrics`, you got a wall of numbers. What do they mean?

## The four numbers, in order

```
n (items)              : 4
coverage (M)           : 1.0000
coverage (per analyst) : 1.0000
κ_C(η, consensus)      : +1.0000
κ_F(η)                 : +1.0000
κ_F*(β) (inter-analyst): undefined
```

### `coverage` — the participation gate

`cov(η) = fraction of items where the model produced a substantive verdict (good or bad, not abstain)`.

This is your **first sanity check**. If it's low, nothing else in the report is fully informative — the kappa metrics are restricted to substantive items, so a 0.3 coverage means you're scoring `M` on 30% of the benchmark.

What low coverage usually means:

| Coverage | Likely cause | What to do |
|---|---|---|
| `0.95–1.00` | Normal | Move on to kappa. |
| `0.70–0.95` | Some items are genuinely hard, or you have a small `--max-tokens` and a verbose model | Inspect the `parse_status` field in `η`: `unparseable` means the model talked but didn't say a verdict word. `budget_clipped` means the provider truncated by `max_tokens` — raise it. `sample_failed` means a provider error after retries. |
| `0.30–0.70` | Likely a verification prompt the model finds genuinely ambiguous, or a content-attribution disagreement (see Haiku-style perceptual default) | Inspect the prompts that produced abstains; try the paraphrase axis (`experiments/paraphrase_axis_triangulation.py`). |
| `0.00–0.30` | Often token-budget or model-misconfigured | Check `parse_status` distribution. If lots of `budget_clipped`, bump `--max-tokens` to 2048+. See [`providers.md`](providers.md) for the reasoning-tokens issue. |

**Per-analyst coverage** (`cov_j(η)`) is the analog for each human analyst — useful when authoring a benchmark to spot analysts who abstain a lot (their column has less inferential signal).

### `κ_C(η, consensus)` — agreement with the analysts

Cohen's kappa against the **analyst consensus** `c_i` (strict-majority vote across analysts; abstain on tie or when most abstain). Restricted to items where both `M` and the consensus are substantive.

Reading scale, with caveats:

| Value | Loose label | What it means |
|---|---|---|
| `+1.00` | perfect | `M` and the consensus agree on every substantive item. |
| `+0.80 to +0.99` | strong | `M` reliably tracks consensus; disagreements are isolated. |
| `+0.40 to +0.80` | moderate | `M` agrees better than chance but with notable exceptions. Decompose by tag to find the pattern. |
| `+0.20 to +0.40` | weak | `M`'s verdicts are correlated with consensus but only modestly. Often this is a content-attribution disagreement, not an inferential one. Try the paraphrase axis (`docs/concepts.md`). |
| `0.00 to +0.20` | none | `M` is at or near chance. |
| `< 0.00` | anti-correlated | `M` is systematically disagreeing. Often this is a prompt-reading issue (the model is treating "GOOD" as something other than what the verification prompt says). |
| `undefined` | n/a | Either the substantive subset is empty (raise coverage) or the chance-expected agreement `p_e = 1` (everyone — including `M` — is in a single class on this subset, so kappa has no signal). |

The standard cautions about Landis–Koch labels apply: these are heuristic, not normative. In small-`n` benchmarks (`n < 20`), kappa is high-variance and the labels above are at best directional.

**Switching the reference**: by default the reference is the consensus, but you can compare `M` against any specific analyst:

```
infereval metrics eta.json --reference analyst:physician-a
```

This is informative when analysts disagree among themselves: comparing `M` to each analyst separately can show that `M` is closer to one analyst's column than the other. The paper's discussion of carving-relativity (§5) is exactly this kind of phenomenon — disagreement among competent labelers reflects different ways of carving the domain, and `M` may align with one carving more than another.

### `κ_F(η)` — `M` as the `(m+1)`-th annotator

Fleiss' kappa treats `M` as if it were one more analyst on the panel. Per-item agreement is the pairwise-pair agreement count across all `m+1` annotators, averaged across items, chance-corrected against the pooled marginal distribution.

`κ_F` is different from `κ_C` in two key ways:

1. **Symmetric**. `κ_F` doesn't single out a reference; every annotator contributes equally. This is appropriate when you don't want to privilege analyst consensus over `M`.
2. **Pooled marginals**. The chance-expected agreement is computed from the pooled distribution of all annotators' verdicts. This means `κ_F = κ_C` only by coincidence (typically only when the marginals are symmetric, e.g. under perfect agreement on a balanced item set). At `m = 1`, `κ_F` with `M` as the 2nd annotator is **not** the same number as `κ_C` against that analyst, except in special cases.

Reading `κ_F`: same scale as `κ_C`. What you compare it to is the next metric.

### `κ_F*(β)` — the inter-analyst baseline

This is **the most important reference number** when `m ≥ 2`. It's Fleiss' kappa computed over the analysts alone (no `M`).

The paper's Remark 5 makes the point: `κ_F*(β)` tells you how well the analysts agree with each other before `M` is in the picture. It's the ceiling above which `M` is doing something the analysts don't do. It's also the floor: if `κ_F*(β) = 0.6`, then `M` reaching `κ_F = 0.5` is participating in the practice at a level not far from the analysts' own internal agreement — which is a strong result.

| Comparison | What it tells you |
|---|---|
| `κ_F(η) ≈ κ_F*(β)` | `M`'s inclusion doesn't lower inter-annotator agreement — it participates at human-analyst-level coherence. |
| `κ_F(η) > κ_F*(β)` | `M` is *more* consistent with the analyst consensus than the analysts are with each other. Plausible if `M` is just tracking the median, but worth investigating. |
| `κ_F(η) << κ_F*(β)` | `M` is systematically disagreeing with the analyst community. Decompose by tag. |
| `κ_F*(β) = undefined` | Either `m < 2` (no inter-analyst comparison possible) or the analysts are unanimous on every item (no signal). Single-analyst benchmarks are perfectly fine — you just lose this comparison. |

If your benchmark has `m = 1`, expect `κ_F*` to always be undefined and rely on `κ_C` for headline numbers.

## Decompositions: when the overall number isn't enough

A single `κ_C = 0.40` could mean many different things:

- `M` is uniformly mediocre across all items;
- `M` is perfect on some items and chance on others;
- `M` is perfect on "easy" items (base inferences) and consistently wrong on "hard" ones (defeaters);
- `M` is fine on items with a particular tag and broken on others.

The first three are inferentially different and the fourth is a smoking gun for content-attribution issues. **Decomposition is how you tell which it is.**

### By tag

```
infereval metrics eta.json --benchmark bench.json \
    --by-tag base-inference \
    --by-tag irrelevant-addition \
    --by-tag defeater
```

Produces a separate `n / coverage / κ_C / κ_F / κ_F*` block per tag. **This is the single most useful tool the framework gives you for diagnosis.** A pattern like:

```
By tag: base-inference        κ_C = +1.0000
By tag: irrelevant-addition   κ_C = -1.0000
By tag: defeater              κ_C = +1.0000
```

tells you a precise story: `M` handles base inferences and defeaters but is systematically wrong on irrelevant additions. This is exactly the cross-model finding from `experiments/paraphrase_axis_triangulation.py`: Claude Haiku 4.5 vs. the paper's analyst row.

Choose tag conventions when authoring the benchmark with this decomposition in mind. `["base-inference"]`, `["irrelevant-addition"]`, `["defeater"]` are the obvious ones for RSR-style work; add domain-specific tags too (`["nighttime"]`, `["coinfection"]`).

### By RSR target

```
infereval metrics eta.json --benchmark bench.json \
    --by-rsr-target '{"X": ["bd"], "A": ["ab"]}'
```

Filter to items probing one specific target inference. Useful when a benchmark covers multiple target inferences (multiple `rsr_target` groupings) and you want the per-target story.

## Edge cases the framework reports rather than hides

The metrics functions return `None` (with a logged warning) rather than raise. These cases are not bugs:

- **`κ_C` undefined when substantive subset is empty.** All items have `M` abstain, or the reference abstain, or both. No items to compare.
- **`κ_C` undefined when `p_e = 1`.** On the substantive subset, every item is the same class (all `good` or all `bad`) for both `M` and the reference. Chance and observed are both 1.0; their difference is 0/0. This often appears on small tag subsets where the analysts unanimously labeled one way and `M` matched.
- **`κ_F` undefined when no items have all-substantive annotations.** Same idea as `κ_C` empty `S`, applied across the full annotator set.
- **`κ_F*` undefined when `m < 2`.** Single-analyst benchmarks have no inter-analyst comparison.
- **`κ_F*` undefined when analysts are unanimous.** `m ≥ 2` analysts agreeing perfectly on every item gives `P̄_e = 1` and chance and observed are both 1.0. No signal.

Each of these returns `null` in the JSON output and `"undefined"` in the text / markdown output, with the reason logged at WARNING. They are diagnostic, not failures — they tell you something concrete about the structure of your benchmark or the model's behavior.

## A worked reading: the live Haiku result from the M9 demo

We ran Claude Haiku 4.5 against the stop-sign benchmark with the original `δ(ra) = "a is red"` and got:

```
n (items)              : 4
coverage (M)           : 1.0000
κ_C(η, consensus)      : +0.2000
κ_F(η)                 : +0.0000
κ_F*(β) (inter-analyst): undefined        // m = 1

By tag: base-inference         κ_C undefined  (n=1; only one substantive item — p_e = 1)
By tag: irrelevant-addition    κ_F = -1.0000  (n=2; perfect anti-correlation!)
By tag: defeater               κ_C undefined  (n=1; same reason as base-inference)
```

Step-by-step reading:

1. **Coverage is 1.00.** No abstains; the model committed on every item. Good baseline.
2. **Overall κ_C = +0.20.** Above chance but well below agreement. Something is going wrong.
3. **By-tag decomposition is the smoking gun.** `irrelevant-addition: κ_F = -1.00` means `M` perfectly disagrees with the analyst on every item tagged `irrelevant-addition`. Those are exactly the two items where `Γ = {sa, n}` and `Γ = {sa, n, nr}` — the nighttime / non-reflective additions.
4. **Hypothesis**: `M` reads `is red` as a *perceptual* claim (nighttime defeats visibility), not an intrinsic claim. Both readings are coherent; they just denote different things.

Following up on the hypothesis is what `experiments/paraphrase_axis_triangulation.py` does: hold the analyst row constant, vary `δ(ra)`, see whether the disagreement comes from the bearer carving. (It does. The intrinsic phrasing `a has the standard color of stop signs` flipped row-1 to `good` and raised `κ_C` to `+0.50`.)

This is the methodology working: it gave a single number (`+0.20`), then a decomposition that localized the disagreement (`irrelevant-addition: -1.00`), then a hypothesis the analyst could test by varying `δ`. Each step in this chain is a concrete output of the framework.

## When the numbers are surprising

If the kappa numbers don't match your prior intuition for the model, the order of diagnostic steps is:

1. **Coverage low?** Token-budget or prompt-ambiguity issue. Fix `--max-tokens`; inspect a few `unparseable` samples in `η`.
2. **Decompose by tag.** Is the disagreement concentrated in one tag? That's almost always content-attributional.
3. **Inspect the actual prompts.** `infereval evaluate --dry-run` prints what the model is seeing. Verify the framing is what you intended.
4. **Probe with reasoning enabled.** Outside the framework, ask the model the same question with room to explain. Often the model's reasoning makes its content-attribution explicit (Claude's verbatim "we cannot infer that the sign *displays* its standard color — only that it *possesses* that color as a property" is the canonical example).
5. **Vary `δ`.** If the disagreement is content-attributional, swapping the bearer phrasing for the analyst's reading should recover agreement. Run a second benchmark with the variant; see `experiments/paraphrase_axis_triangulation.py` for the pattern.

## Where to go next

- [`concepts.md`](concepts.md) for the methodology's terms.
- [`authoring_benchmarks.md`](authoring_benchmarks.md) if your interpretation suggests you need a richer benchmark.
- [`providers.md`](providers.md) for per-provider quirks (specifically, what to set `--max-tokens` to).
- `experiments/paraphrase_axis_triangulation.py` for a worked example of the diagnostic chain above.
