# Construct-validity workflow: end-to-end

> **Audience.** You're the analyst (or the team) producing reproducible, well-founded evidence for a claim of inferential mastery against some carving. You have access to a frontier LLM via API, a domain you want to evaluate, at least one domain expert willing to label items, and `infereval` ≥ 0.5.1.
>
> **What this document is.** A practitioner's guide that walks the full programme — from picking the domain to publishing the artifacts — using the framework as far as it can take you and being explicit about what it can't. Companion document to [`closing_the_construct_validity_gap.md`](closing_the_construct_validity_gap.md), which records what was shipped.

## The shape of the workflow

Nine phases. The framework handles 1–7; phases 0, 4 (in part), and 8 are research-program work that the framework supports but cannot do for you.

| Phase | What you do | What the framework does | What you alone do |
|---|---|---|---|
| 0 | Plan the experiment | nothing — design comes first | pick D, B, δ, scope, panel |
| 1 | Author the benchmark | validate structure | author item content |
| 2 | Run the evaluation | sample M, log everything | provide the API key |
| 3 | Run analytical checks | `structure`, `model`, `sweep` | inspect anomalies |
| 4 | Cross-panel / replication | compute cross-panel κ once panel 2 exists | recruit panel 2; rerun benchmark |
| 5 | Write the claims file | validate structure + verdict logic | declare scope, sense, position |
| 6 | Generate the report | render Markdown with auto-collected negatives | nothing |
| 7 | Publish artifacts | reproducible JSON + hashes | host & cite |
| 8 | Stand behind the claim | nothing — interpretation is yours | argue the case in your write-up |

The framework's *cheap-to-do-it-right, expensive-to-cut-corners* asymmetry shows up at every phase. Skipping a phase is fine; doing it without declaring you skipped it isn't. The report verdict refuses to render ✅ "defensible" when the skips are not at peace with the declared scope.

---

## Phase 0: Plan the experiment

This phase is entirely in your head and on paper. Get it right before you write any code.

### 0.1 Pick the domain D

Domains that admit expert labeling of inferential examples: clinical reasoning (the running example below), contract law, classical logic, software engineering, electrical-circuit reasoning, chess endgames. Domains that don't: aesthetic judgment, ethical intuition, anything where "competent practice" isn't well-defined.

The framework is *carving-relative*. There is no domain-independent fact about "model mastery of D"; there's only mastery of D *under the carving you supply*. If you pick a domain where competent labelers will disagree about how to carve it, you'll get a benchmark that doesn't generalise. That's not a framework failure; it's the methodology being honest.

### 0.2 Pick the carving — bearers B, expression function δ

The bearer set B is the analyst's choice of propositional atoms over which D's inferences are reasoned about. Three rules of thumb:

1. **Atoms, not compounds.** If two bearers can be expressed as a conjunction of cleaner ones, the cleaner ones go in B and the compound is recovered as a Γ-set.
2. **Operationalisable English.** Every bearer must have a δ-image that a domain expert reads unambiguously. "Patient is sick" fails; "Patient has acute dyspnea" works.
3. **Roughly 10–30 bearers per benchmark.** Fewer and the inferential structure is impoverished; more and the analyst can't keep them straight when labeling. The pulmonology benchmark uses 20.

Write down δ as a dictionary, like the pulmonary-edema benchmark does:

```json
{
  "bi":   "the patient has bilateral pulmonary infiltrates on imaging",
  "ad":   "the patient has acute dyspnea",
  "cpe":  "the patient has cardiogenic pulmonary edema",
  "ards": "the patient has acute respiratory distress syndrome"
}
```

If you anticipate paraphrase robustness checks (R10 — and you should), record alternative phrasings in each bearer's `paraphrases` list now. Per the v0.3.1 mechanic, variant 0 always uses `expression`; variant k≥1 uses `paraphrases[k-1]` per bearer with fallback to the canonical.

### 0.3 Decide the scope of the claim you intend to make

This is the single decision that most determines what evidence you'll need to collect. Three options:

- **`items_in_benchmark`** — the narrowest. You claim mastery of the specific implications listed in β; you don't generalise to D, much less beyond. Requires only the within-benchmark hygiene (structural coherence + sensitivity sweep). Appropriate for demonstration-stage work.

- **`domain_D_as_sampled`** — middle. You claim mastery of D as represented by β's coverage. Requires the above plus paraphrase robustness, cross-panel agreement, held-out items.

- **`general_capacity`** — broadest. You claim mastery of inferential reasoning as a general capacity that happens to be measured here. Requires all of the above plus training-data separation, cross-domain comparison, and replication. **Also requires R19 (carving-indexed framing of in-principle claims) to be acknowledged with non-empty notes**, or the report's verdict auto-downgrades to NOT defensible regardless of the rest.

Pick the narrowest scope that does the work your write-up needs. Broader scopes look more ambitious but make you do strictly more checks. Most demonstration projects should pick `items_in_benchmark` and earn `domain_D_as_sampled` only after the second analyst panel is in place.

### 0.4 Recruit the analyst panel(s)

The framework records analyst declarations but cannot vet their competence. Two responsibilities, both yours:

- **Document competence (R1).** Each analyst's `AnalystModel.notes` field should record training, credentials, or other grounds for treating their verdicts as a defensible reference for D's practice. "Board-eligible pulmonologist, 12 years bedside experience" beats "physician".
- **For R4 (independent reference check): recruit a second panel.** This is the most consequential research-program piece. If only one panel labels β, you can't compute κ_F* (inter-analyst Fleiss) and `cross_panel_kappa`. Plan for two panels from the start; the second one need not be large (one or two additional experts on a 30-item benchmark gives you the cross-panel signal).

If you can only recruit one panel for the first pass, that's fine. The framework will tell you what's unavailable; the construct-validity report will track the missing check; the verdict will be honest about what's defensible from m=1. You can then add a second panel in a later run and re-render.

### 0.5 Decide which model(s) to evaluate

Pick the model **before** authoring items. The `construction_metadata.authored_blind_to_models` field is the construct-validity hygiene check for R8: it says "the author of this item had not observed model X's behavior on a draft of this item." If you write the benchmark, run it against M, see something interesting, then rewrite items, the rewrite items aren't blind. You can still use them, but you have to declare them as not-blind, and the report will track the omission.

For comparative work — what we did with the pulmonology benchmark across six models — declare every model up front. The blind list per item names *all* the models the author was blind to; if the list is empty, the item is not held-out against anything.

---

## Phase 1: Author the benchmark

The benchmark JSON is the single source of truth. Edit it directly; validate often.

### 1.1 The skeleton

```json
{
  "schema_version": "1.0",
  "id": "my-domain-benchmark-v0.1",
  "title": "...",
  "domain": "...",
  "description": "...",
  "bearers": { ... },
  "analysts": [ ... ],
  "primary_panel": "primary",
  "factors": { ... },
  "factor_constraints": { "min_items_per_cell": 3 },
  "items": [ ... ],
  "references": [ ... ]
}
```

See [`authoring_benchmarks.md`](authoring_benchmarks.md) for the full schema. The construct-validity-relevant fields are highlighted below.

### 1.2 Declare analysts with panels (R4, v0.3.3)

Even if you start with one panel, declare it explicitly:

```json
"analysts": [
  {
    "id": "pulmonologist-a",
    "display_name": "Pulmonologist A",
    "notes": "Senior pulmonologist, 12 years bedside experience in differential diagnosis of pulmonary edema",
    "panel": "primary"
  },
  {
    "id": "pulmonologist-b",
    "display_name": "Pulmonologist B",
    "notes": "Board-eligible pulmonologist, training fellowship at MGH",
    "panel": "reviewer"
  }
],
"primary_panel": "primary"
```

The validator enforces that *either* all analysts have a panel or none do; partial-panel benchmarks are rejected with a specific error message. If you only have one panel today, leave `panel` off every analyst and add `primary_panel` later when the second panel comes online.

### 1.3 Declare factors (R7, v0.3.0)

Choose factors that name the inferential dimensions you want to characterise. The pulmonology benchmark could declare:

```json
"factors": {
  "side_premise_type": ["base", "supporter", "defeater", "mixed-evidence"],
  "target_inference": ["T1", "T2", "cross-cutting"]
},
"factor_constraints": {
  "min_items_per_cell": 2
}
```

The validator rejects items declaring a factor key not in `factors`, items declaring a level value not in the declared levels list, *and* benchmarks where any cell of the crossed design has fewer than `min_items_per_cell` items. A 4×3 design at `min_items_per_cell=2` needs at least 24 items; check the math before you author 12 and find out at validation time.

### 1.4 Author items with full provenance (R5, R8, R9, v0.3.2)

Every item should carry:

```json
{
  "id": "c2",
  "premises": ["bi", "ad", "el"],
  "conclusions": ["cpe"],
  "analyst_verdicts": ["good", "good"],
  "tags": ["supporter", "T1", "biomarker", "dialectical-low"],
  "rsr_target": {"X": ["bi", "ad"], "A": ["cpe"]},
  "factor_levels": {
    "side_premise_type": "supporter",
    "target_inference": "T1"
  },
  "construction_metadata": {
    "authored_by": "physician-c",
    "authored_on": "2026-04-15",
    "authored_blind_to_models": ["claude-opus-4-7", "gpt-5", "gemini-2.5-pro"],
    "source": "Sanford Guide to Antimicrobial Therapy 2025, Chapter 12"
  },
  "references": [
    {
      "citation": "Maisel AS et al. (2002). N Engl J Med 347(3):161-167.",
      "doi": "10.1056/NEJMoa020233",
      "note": "Elevated BNP supports cardiogenic etiology over non-cardiogenic."
    }
  ]
}
```

Notes:

- **`analyst_verdicts`** must have one entry per declared analyst, in the order they appear in `analysts`. For two panels each with one analyst, that's two verdicts.
- **`tags`** carries inferential-role identifiers the framework recognises (`supporter`, `defeater`, `irrelevant-addition`, `base-inference`) — used by `infereval structure`'s RSR role-consistency check.
- **`rsr_target`** declares which target inference this item probes RSR around (per Allen 2026's RSR definition); needed for the structural check.
- **`factor_levels`** positions the item in your declared crossed design.
- **`construction_metadata.authored_blind_to_models`** is the key R8 declaration. Lying about it (or omitting it for a non-blind item) makes the rest of the report dishonest.
- **`references`** carries the literature anchoring; the construct-validity report shows them under the Evidence section.

### 1.5 Add benchmark-level references (R20, v0.2.2)

```json
"references": [
  {
    "citation": "Ranieri VM et al. ARDS Definition Task Force (2012). JAMA 307(23):2526-2533.",
    "doi": "10.1001/jama.2012.5669",
    "note": "Defining reference for the ARDS target (T2)."
  }
]
```

Corpus-level provenance — the papers/guidelines/dialogues the benchmark is built on.

### 1.6 Validate

```bash
infereval validate path/to/benchmark.json
infereval describe path/to/benchmark.json
```

`validate` runs the full Pydantic schema check + the structural validators (factor-level consistency, panel consistency, per-cell minimum). `describe` shows you the summary including the new sections from v0.3.x:

- `bearers (...)` — the dictionary with English expressions
- `references:` — corpus / bearer / item counts
- `factorial design (...)` — total cells, populated cells, underpopulated cells if any
- `paraphrase variants:` — count + coverage line
- `analyst panels:` — per-panel κ_F* + cross-panel κ_C when ≥ 2 panels
- `construction provenance:` — annotated item count, unique authors, date range, blinded-to models

If `describe` doesn't show what you intended, fix the JSON before going further.

---

## Phase 2: Run the evaluation

### 2.1 The baseline run

```bash
infereval evaluate path/to/benchmark.json \
  --provider openai --model gpt-5.5 \
  --n-samples 3 --temperature 0.0 --max-tokens 1024 \
  --run-id pulm-gpt55-2026-05-20 \
  --log out/pulm-gpt55-run.jsonl \
  -o out/pulm-gpt55-eta.json
```

What the framework records (per R20):

- The benchmark's SHA-256 hash on `Evaluation.benchmark_hash` (tamper detection).
- Every sample call with timestamps and token counts (in the JSONL log).
- The exact decoding params used (`ProviderParams` block of the evaluation JSON).
- The exact verification prompt used (resolved from the benchmark's override or the framework default).
- The endorsement config (`n_samples`, tie-break rule).
- The framework version that produced the artifact.

### 2.2 Paraphrase-axis sweep (R10, v0.3.1)

If your bearers have `paraphrases`, run the cycle to get one evaluation per variant:

```bash
infereval evaluate path/to/benchmark.json \
  --provider openai --model gpt-5.5 \
  --n-samples 3 --temperature 0.0 \
  --paraphrase-cycle \
  -o out/pulm-gpt55-eta.json \
  --log out/pulm-gpt55-run.jsonl \
  --run-id pulm-gpt55-paraphrase
```

This produces `pulm-gpt55-eta-v0.json`, `pulm-gpt55-eta-v1.json`, etc. — one per variant. Each evaluation file records its `paraphrase_variant` field so artifacts are unambiguous after the fact.

### 2.3 Multi-model evaluation

For cross-family comparison (the experiment we did with pulmonology), run the same benchmark against each model with the same parameters. The reproducibility infrastructure ensures each run is independently verifiable; the SHA-256 hash confirms every run used the same benchmark.

---

## Phase 3: Analytical checks

Three commands. Run them in any order; they're independent.

### 3.1 Structural coherence — `infereval structure` (R13, v0.4.0)

```bash
infereval structure out/pulm-gpt55-eta.json \
  --benchmark examples/pulmonary_edema/benchmark.json
```

Three checks fire:

1. **Containment closure** — sanity: self-implications (Γ ∩ Δ ≠ ∅) are in I_M by construction.
2. **RSR role consistency** — for each item carrying `rsr_target` + a role tag (`supporter` / `defeater` / `irrelevant-addition`), the model's verdict is compared against the verdict the role *predicts* given the base-inference verdict. Anomalies are listed item-by-item with the explanation.
3. **Base-case stability** — when a target has multiple base-inference items, the model should give the same verdict on all of them.

The output is human-readable Markdown-ish text; the per-anomaly explanations name the item id, the role, the base verdict, the predicted verdict, and the actual verdict. The pulmonology benchmark's Gemini 2.5 Pro evaluation correctly surfaces a9 as the one anomaly. **This is the philosophically central check** — it's where aggregate agreement gets distinguished from structural mastery.

If your scope is `items_in_benchmark` or higher, you must run this check before the report verdict can be ✅ defensible.

### 3.2 Factor-effects model — `infereval model` (R7, R12, v0.4.1)

```bash
infereval model out/pulm-gpt55-eta.json \
  --benchmark path/to/benchmark.json
```

Fits a logistic regression of agreement (with the analyst consensus, by default) on the declared factor levels with item-clustered standard errors. Output:

```
factor-effects model of agreement
=================================

evaluation:    pulm-gpt55-2026-05-20
benchmark:     pulmonary-edema-differential-v0.1
observations:  84 (after excluding 3 abstain sample(s))
items:         29
factors:       2 declared
pseudo-R²:     0.182

Per-factor joint Wald tests:
  side_premise_type    < 0.001 ***
  target_inference     0.245

Effects (log-odds relative to baseline level):
  factor             level     coef     SE     p          95% CI
  side_premise_type  defeater  -1.92  0.31    < 0.001 *** [-2.53, -1.32]
  side_premise_type  mixed     -0.42  0.45    0.345      [-1.30, +0.46]
  target_inference   T2        -0.12  0.18    0.516      [-0.46, +0.23]
  target_inference   cross-c.  +0.04  0.18    0.825      [-0.31, +0.39]

Methodology:
  Fixed-effects logistic regression with item-clustered standard errors.
  Approximates the per-item random-effect structure of a proper GLMM.
  Reference for 'agreement': 'consensus'.
```

Read the per-factor Wald row: `side_premise_type < 0.001 ***` means the design factor explains significant variance in agreement (substantively informative); `target_inference 0.245` means no detected effect of which target the item probes. Reading the effects rows: `defeater` items reduce log-odds of agreement by ~1.92 versus the baseline level (which is alphabetically-first; check the declared levels order).

This is the "main effect of side-premise type, p < 0.001" output that R12 motivates.

### 3.3 Sensitivity sweep — `infereval sweep` (R11, v0.4.2)

```bash
infereval sweep path/to/benchmark.json \
  --provider openai --model gpt-5.5 \
  --vary n_samples --values 1,3,5,7 \
  --out-dir out/sweep_n_samples/
```

Runs the benchmark four times — once with each value — and bundles the metrics into `out/sweep_n_samples/sweep-summary.json`. The console output ends with a one-sentence stability verdict:

- "κ_C range = 0.012; agreement is stable across the sweep range."
- "κ_C range = 0.072; agreement is moderately sensitive to the swept parameter."
- "κ_C range = 0.184; agreement varies substantively across the sweep range — consider tighter parameter choices or a wider analyst panel."

Run sweeps over the parameters whose choice you can't justify a priori. The pulmonology demo had no reason to choose `n_samples=3` over `n_samples=5`; a sweep showing the κ_C range is small justifies the choice. Run a paraphrase-variant sweep separately (`--vary paraphrase_variant --values 0,1,2`) to check content-vs-form robustness.

---

## Phase 4: Cross-panel + replication (the research-program part)

This is where the framework's infrastructure work meets your institutional work.

### 4.1 Second analyst panel (R4)

Recruit a second pulmonologist. Have them label the same items independently of the first (blind to the first's verdicts and to any model output). Edit the benchmark JSON:

```json
"analysts": [
  {"id": "pulm-a", "panel": "primary", "notes": "..."},
  {"id": "pulm-b", "panel": "primary", "notes": "..."},
  {"id": "pulm-c", "panel": "reviewer", "notes": "..."}
],
"primary_panel": "primary",

"items": [
  {
    "id": "c1",
    "premises": ["bi", "ad"],
    "conclusions": ["cpe"],
    "analyst_verdicts": ["good", "good", "bad"]
  }
]
```

The verdict tuple length must equal the analyst count. Re-run `infereval describe` to see the new section:

```
analyst panels: 2 (primary = primary)
  primary    pulm-a, pulm-b  (n=2)  κ_F* = +0.78
  reviewer   pulm-c          (n=1)  κ_F* = undefined (n<2)
  cross-panel κ_C(primary vs reviewer): +0.62 over 28/29 substantive items
```

If `cross-panel κ_C` is high (above the κ_C the model achieves against the primary panel), the primary panel's signal is corroborated by the independent reviewer — R4 is satisfied. If it's low, you have shared-error agreement to worry about; the report's verdict will reflect this.

### 4.2 Replication (R15)

Strict replication: same benchmark, fresh model sampling (a new run on a different day). Already handled by re-running `infereval evaluate`; the SHA-256 hash confirms the benchmark didn't change.

Scientific replication: fresh benchmark constructed independently by a second author following the same construction procedure, evaluated against the same model, statistics compared to the first. This is real research-program work; the framework can't do it for you, but the construct-validity report tracks `replication_attempted` as a declared check and downgrades the verdict at `scope=general_capacity` when missing.

### 4.3 Cross-domain comparison (R14)

If your scope is `general_capacity`, evaluate M against a benchmark in a comparison domain D′. The framework can run two benchmarks against the same model; you write up the comparison. Track `cross_domain_comparison_run` in the claims file.

---

## Phase 5: Write the claims file

```bash
infereval report --init-claims path/to/claims.json
```

This produces a stub like:

```json
{
  "mastery_sense": {
    "sense": "evaluative",
    "description": "FILL IN: the analyst's articulation of what mastery means here."
  },
  "scope": {
    "scope": "items_in_benchmark",
    "justification": "FILL IN: why this scope is appropriate."
  },
  "constitution": {
    "position": "evidence_of_mastery",
    "justification": "FILL IN: brief explanation of the position taken."
  },
  "carving": {
    "acknowledges_carving_indexed": false,
    "notes": "FILL IN if acknowledges_carving_indexed=true."
  },
  "competing_explanations": {
    "paraphrase_sweep_run": false,
    "sensitivity_sweep_run": false,
    "structural_check_run": false,
    "cross_panel_check_run": false,
    "independent_reference_panel_used": false,
    "held_out_items_used": false,
    "training_data_separation_verified": false,
    "cross_domain_comparison_run": false,
    "replication_attempted": false
  }
}
```

Fill in **every** placeholder. The framework rejects the report render if any required field is missing.

### 5.1 R16 — Mastery sense

Pick one of `evaluative` / `generative` / `standing` / `combination`. Most measurement-from-prompt-response work is `evaluative` — you're asking the model to evaluate inferences, not produce them in unprompted generation. Don't claim `standing` (a dispositional competence) unless your evidence supports it; the framework doesn't measure dispositions directly.

Description in your own words, 1-3 sentences. The reviewer should be able to read it and know exactly what mastery would look like *if* the model had it.

### 5.2 R17 — Scope

Pick the narrowest scope your evidence justifies. The verdict's required-checks set depends on this choice; broader scopes need strictly more checks.

`justification` explains why this scope is right for *your* benchmark. For the pulmonology demo: "m=1 analyst, placeholder labels, demonstration stage — generalisation to D requires the real labels plus the second panel before any broader claim is warranted."

### 5.3 R18 — Constitution vs evidence

`evidence_of_mastery` is the standard scientific posture: high κ_C is evidence supporting a deeper claim. `constitutive_of_mastery` is Brandom's structural-behavioural reading: agreement plus structural coherence *is* mastery in the inferentialist sense — there's no further fact to evidence.

Both are defensible; pick the one your write-up will argue for. The report renders the position verbatim under section 3.

### 5.4 R19 — Carving acknowledgement

If your scope is `items_in_benchmark`, leave `acknowledges_carving_indexed=false` and `notes` empty — no in-principle claims are being made, so no carving-indexed framing is needed.

If your scope is broader (`domain_D_as_sampled` or `general_capacity`), you **must** set `acknowledges_carving_indexed=true` AND write non-empty `notes` explaining the carving used. The notes might say: *"The carving used is B = {20 bearers for pulmonary edema differential diagnosis} with δ as supplied in benchmark.json's bearer dictionary. Per Allen (2026) Remark 9, all in-principle claims in §6 are framed in carving-indexed form: 'mastery of pulmonary-edema reasoning under the B/δ carving' rather than unrestricted 'mastery of pulmonary medicine.'"*

If you skip this at scope ≥ `domain_D_as_sampled`, the verdict auto-downgrades to NOT defensible regardless of how many other checks you ran.

### 5.5 R4 etc. — Competing-explanation checks

Mark `true` only for checks you actually ran. Lying here makes the entire report dishonest; the framework can't detect dishonesty but readers will.

- `structural_check_run`: you ran `infereval structure`.
- `sensitivity_sweep_run`: you ran `infereval sweep`.
- `paraphrase_sweep_run`: you ran `infereval evaluate --paraphrase-cycle`.
- `cross_panel_check_run`: you recruited a second panel, the cross-panel κ was computed and reviewed.
- `independent_reference_panel_used`: a second panel labeled the same items independently of the first.
- `held_out_items_used`: each item's `authored_blind_to_models` includes M.
- `training_data_separation_verified`: temporal separation via `authored_on` OR a structural check against M's training corpus.
- `cross_domain_comparison_run`: M was evaluated on a comparison-domain benchmark.
- `replication_attempted`: a fresh benchmark following the same construction procedure was built and evaluated.

---

## Phase 6: Render the report

```bash
infereval report \
  --evaluation out/pulm-gpt55-eta.json \
  --benchmark path/to/benchmark.json \
  --claims path/to/claims.json \
  --structure out/structure-report.json \
  --sweep out/sweep_n_samples/sweep-summary.json \
  --model-fit out/model-fit.json \
  -o report.md
```

(The `--structure`, `--sweep`, `--model-fit` inputs are optional; supply whichever you ran. Missing inputs show as `NOT SUPPLIED` in the Evidence section.)

### 6.1 The report shape

Six sections + the new Phase 3.2 section 4b:

1. **Identity** — evaluation id, benchmark id, model, run date, item count, analyst count.
2. **Summary metrics** — coverage, κ_C, κ_F, κ_F*.
3. **Construct-validity claims** — your declarations from the claims file, rendered as text.
4. **Evidence** — auto-collected from the optional Phase 2 artifacts.
5. **Negative findings** *(4b — auto-collected from structure / sweep / model-fit, see below)*.
6. **Unaddressed competing explanations** — the list of false flags in `competing_explanations`.
7. **Summary verdict** — ✅ / ⚠️ / ❌ with rationale.

### 6.2 The negative-findings section (4b)

The framework auto-scans your three optional artifacts for findings that weaken or complicate the mastery claim:

- **Structural anomalies** from `--structure`: each item flagged by `rsr_role_consistency` or `base_case_stability`.
- **Sweep instability** from `--sweep`: any verdict that isn't "stable across the sweep range".
- **Factor-effects null findings** from `--model-fit`: factors with Wald p > 0.05 (the experimentally-controlled factor being null is *good* for content-vs-form discrimination; the substantive-treatment factor being null is *bad* — context determines which).

These render by default. To suppress them, add `--suppress-negatives` — at which point:

1. The body of section 4b is replaced by a suppression banner naming the flag.
2. The report header gains a `Negative-findings suppression: ENABLED` warning visible at the top.
3. The Summary verdict downgrades one tier.

The asymmetry is intentional: it is cheap to surface failures correctly and expensive to suppress them.

### 6.3 The summary verdict

Deterministic from claims + flags. Three possibilities:

- **✅ Defensible** — all required checks for the declared scope are marked run; carving acknowledged + documented when scope is broader than `items_in_benchmark`.
- **⚠️ Partially defensible** — some required checks missing.
- **❌ Not defensible** — majority of required checks missing, or carving not acknowledged at scope ≥ `domain_D_as_sampled`.

The rationale block under the verdict names exactly which checks are present and which are missing. A reviewer can read the verdict, the rationale, and the negative-findings section in 30 seconds and know what to question.

---

## Phase 7: Publish the artifacts

Reproducibility comes from publishing the full artifact set:

1. **The benchmark JSON.** With `schema_version` declared (`"1.0"`).
2. **Per-model evaluation JSONs.** Each carries `benchmark_hash` for tamper detection.
3. **JSONL run logs.** One event per sample, full audit trail.
4. **The structure / model / sweep outputs.** Same provenance discipline.
5. **The claims file.**
6. **The rendered report.**

A consumer who has all six can re-validate the benchmark, recompute every metric, and re-render the report from scratch — every claim is grounded in artifacts a reviewer can inspect.

Track them in version control (the `experiments/results/` layout we use in the bundled pulmonology study is a good model). The SHA-256 hashes in the evaluation JSONs guarantee no silent rewriting of the benchmark between the evaluation and the report.

---

## Phase 8: Stand behind the claim

Writing up the result is yours alone. The framework's job ends at the report; what your paper or post says is your responsibility.

Three discipline points the framework's output gives you:

1. **Quote the verdict.** "The construct-validity report renders ⚠️ partially defensible at scope `domain_D_as_sampled`; specifically, the cross-panel check ran but replication has not been attempted." Reviewers can hold you to this.

2. **Don't override the scope.** If the report says ⚠️ at `domain_D_as_sampled`, your write-up shouldn't claim mastery at `general_capacity`. The framework can't stop you, but the report's existence on the same artifact set will contradict you.

3. **Carving-indexed framing in the prose.** "GPT-5.5 demonstrates partial mastery of cardiogenic-vs-ARDS pulmonary-edema reasoning *under the B/δ carving of the v0.1 benchmark*" beats "GPT-5.5 understands pulmonary medicine."

---

## What you can't get from this workflow

After everything: even with two panels, structural checks, factor model, sensitivity sweeps, paraphrase robustness, cross-domain comparison, and a clean ✅ verdict, you have:

- Evidence of agreement at the stated scope, with structural coherence properties, robust to your tested methodological choices, replicated independently.
- The carving-indexed framing of any in-principle claim.

You do not have:

- A model-independent fact about "mastery of D".
- Settlement of whether agreement is constitutive of or evidence for mastery in some deeper sense.
- Assurance that the carving you chose is the one a competent practitioner *would* choose.

The framework doesn't help with any of these — they're not the kind of thing tooling can help with. The methodology is honest about them; your write-up should be too.

---

## Quick reference: the full command sequence

```bash
# Phase 1: validate the benchmark
infereval validate benchmark.json
infereval describe --items benchmark.json

# Phase 2: evaluate
infereval evaluate benchmark.json \
  --provider openai --model gpt-5.5 \
  --n-samples 3 --temperature 0.0 \
  --paraphrase-cycle \
  --run-id myexpt-2026-05-20 \
  --log out/run.jsonl -o out/eta.json

# Phase 3.1: structural checks
infereval structure out/eta.json --benchmark benchmark.json

# Phase 3.2: factor model
infereval model out/eta.json --benchmark benchmark.json

# Phase 3.3: sensitivity sweep
infereval sweep benchmark.json \
  --provider openai --model gpt-5.5 \
  --vary n_samples --values 1,3,5,7 \
  --out-dir out/sweep/

# Phase 5: claims stub
infereval report --init-claims claims.json
# (edit claims.json, fill in every FILL IN)

# Phase 6: render report
infereval report \
  --evaluation out/eta.json \
  --benchmark benchmark.json \
  --claims claims.json \
  --structure out/structure.json \
  --sweep out/sweep/sweep-summary.json \
  --model-fit out/model-fit.json \
  -o report.md
```

That's the full workflow. Add cross-panel (Phase 4.1) and replication (Phase 4.2) as the research-program work proceeds; re-render the report each time to update the verdict.

## Related reading

- [`concepts.md`](concepts.md) — the methodology's vocabulary and the relationship between the inferentialist framework, the implication-space machinery, and the evaluation primitives.
- [`authoring_benchmarks.md`](authoring_benchmarks.md) — full schema reference for the benchmark JSON.
- [`interpreting_metrics.md`](interpreting_metrics.md) — how to read coverage, κ_C, κ_F, κ_F*, and the per-decomposition metrics.
- [`providers.md`](providers.md) — Anthropic / OpenAI / OpenRouter provider configuration.
- [`closing_the_construct_validity_gap.md`](closing_the_construct_validity_gap.md) — what was shipped to make this workflow possible, requirement by requirement.
- [`tutorials/04_pulmonology_visualization.ipynb`](tutorials/04_pulmonology_visualization.ipynb) — visual analytics that complement the CLI tools (matplotlib + pandas; reads the bundled pulmonology artifacts).
