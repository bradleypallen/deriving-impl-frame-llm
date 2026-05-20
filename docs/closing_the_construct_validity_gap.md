# Closing the Construct-Validity Gap in infereval

> **Editor's note.** This document is the implementation-annotated version of the construct-validity programme proposed in `Desktop/closing_the_construct_validity_gap.md` (Allen, May 2026). The original argument is preserved; an **Implementation** callout appears after each requirement and each Phase subsection, pointing to the specific release, PR, and module where the work landed. The coverage table at the bottom now reflects actual coverage as of `infereval` v0.5.1.

## Context

infereval as currently documented provides a clean, reproducible measurement of analyst-model agreement on inferential benchmarks, with the decompositional machinery needed to interpret the resulting agreement statistics. It explicitly leaves the construct-validity work — establishing that agreement on a given benchmark is evidence of *inferential mastery* rather than just agreement on that benchmark — to the analyst and the surrounding research program.

This is a defensible position. The methodology can be used in a deflationary register where the agreement statistic is the whole claim, and in that register most construct-validity worries don't arise. But the framework's natural use case is the one Simonelli's paper motivates: treating strong agreement as evidence of inferential mastery in the framework's structural sense. In that register, a substantial set of construct-validity requirements becomes live — requirements about analyst pool justification, benchmark coverage, competing-explanation controls, structural coherence of the derived frame, and disciplined framing of the resulting claims.

This document records the recommendations originally made for extending infereval, **and the actual extensions that landed in response** (releases v0.3.0 through v0.5.1).

## The requirements

The requirements addressed in this document derive from the question: *what would need to be true of an evaluation methodology for "strong inter-annotator agreement between M and analysts on benchmark β" to constitute evidence of inferential mastery in domain D, rather than just a measurement of agreement on β?* They are grouped into three tiers reflecting how much they're each doing in support of a mastery claim, and organized by the concern they address.

### Tier 1: necessary for any mastery claim from agreement

**Requirements on the analyst pool and reference standard**

- **R1. Documented analyst competence.** The methodology must specify and justify the criteria by which analysts are selected as competent practitioners in the target domain, with documentation of training, credentials, or other grounds for treating their verdicts as a defensible reference for domain practice. *(Messick 1989; Cronbach & Meehl 1955)*

  > **Implementation status: partial — research-program responsibility.** The benchmark schema's `AnalystModel` carries `id`, `display_name`, and `notes` (a free-form text field) where analyst competence can be documented. The framework validates the *presence* of analyst declarations but cannot assess whether the credentials cited are appropriate to the domain. The construct-validity report's claims file (R20, v0.5.0) makes the analyst panel composition part of the disclosed methodology.

- **R2. Computed and reported inter-analyst baseline.** The methodology must compute κ_F*(β) and report it alongside any agreement statistic involving M, with the baseline meeting the conditions for being defined (m ≥ 2 analysts, non-unanimous benchmark items). *(Fleiss 1971; Allen 2026 Remark 4 and Def. 10)*

  > **Implementation status: full.** `infereval.metrics.inter_analyst_fleiss` computes κ_F* over the analyst panel, surfaced by `infereval describe` (top-level baseline line) and `infereval metrics` (per-decomposition). Returns `None` with a logged warning in the conditions Remark 5 calls out (m < 2 or unanimous analysts). Extended in v0.3.3 (Issue #36) with `inter_analyst_fleiss_per_panel` returning the κ_F* per declared panel when the benchmark uses the panel structure (R4).

- **R3. Interpretive framing relative to the baseline.** The methodology must frame agreement claims in explicit relation to κ_F*(β) — neither in isolation nor against an unstated absolute threshold — so that "strong agreement" is operationalized as a specific relationship to the analyst-internal ceiling rather than as an arbitrary kappa value. *(Landis & Koch 1977; Allen 2026 Remark 4)*

  > **Implementation status: full.** `infereval describe`, `infereval metrics`, and the construct-validity report (`infereval report`, v0.5.0) all surface κ_F* alongside κ_C / κ_F so the comparison is immediate. The construct-validity report explicitly relativises the mastery verdict to the declared scope (R17, v0.5.0).

**Requirements on benchmark construction**

- **R5. Documented construction procedure.** The methodology must specify and document the procedure by which β was constructed — bearer selection, item generation, inferential-type coverage, difficulty calibration — so that content-validity arguments are available rather than presumed. *(Messick 1989; Gebru et al. 2021; Bender & Friedman 2018)*

  > **Implementation status: full at item level.** Shipped in v0.3.2 (Issue #34) as the `BenchmarkItem.construction_metadata` field carrying `authored_by`, `authored_on`, `authored_blind_to_models`, and `source`. The framework validates structure (Pydantic types, `extra="forbid"`) but does not enforce content. `infereval describe` surfaces a construction-provenance summary section + per-item annotation in `--items` output.

- **R6. Coverage of inferential types salient in the domain.** The methodology must ensure β includes the range of inferential types the framework treats as constitutive of mastery — monotonic and defeasible cases, RSR-targeted variation around target inferences, and structural relationships among inferences — rather than enumerating items of a single type. *(Hlobil & Brandom 2025; Allen 2026 Remark 5)*

  > **Implementation status: full via tag + factorial-design infrastructure.** The pre-existing `tags` field carries inferential-role identifiers (`supporter`, `defeater`, `irrelevant-addition`, `base-inference`, etc.). The factorial-design metadata shipped in v0.3.0 (Issue #30) adds explicit `factors` + `factor_levels` so the inferential-type axes become first-class. `infereval structure` (v0.4.0) checks RSR role consistency against the resulting design.

- **R7. Multiple items per condition.** The methodology must include multiple distinct items instantiating each condition or inferential type, so that item-level idiosyncrasy can be separated from condition-level effects in the analysis. *(Schütze 1996; Cowart 1997; Baayen, Davidson & Bates 2008; Barr et al. 2013)*

  > **Implementation status: full.** Shipped in v0.3.0 (Issue #30) as `Benchmark.factor_constraints.min_items_per_cell`. The benchmark validator rejects designs that fall short of the declared floor, with an error message listing the underpopulated cells. `infereval describe` surfaces the populated-cell count and the floor-meeting count.

**Requirements on stimulus design**

- **R10. Paraphrase variation under fixed inferential content.** The methodology must include, for each item or each condition, multiple meaning-preserving paraphrases of δ, ctx_Γ, and ctx_Δ, so that agreement attributable to inferential content can be separated from agreement attributable to surface form. *(Allen 2026 Remark 8; Ribeiro et al. 2020; McCoy, Pavlick & Linzen 2019)*

  > **Implementation status: full.** Shipped in v0.3.1 (Issue #32). Promoted the existing `BearerModel.paraphrases` field from documentation-only to runtime-active. New `--paraphrase-variant K` and `--paraphrase-cycle` flags on `infereval evaluate` orchestrate the per-variant runs; outputs auto-suffix with `-vN`. The single most-cited concern in this document's reviewer reactions about content-vs-form sensitivity is now a one-flag operation.

**Requirements on the analysis**

- **R12. Per-cell or per-condition decomposition.** The methodology must report agreement statistics decomposed by inferential type, target inference, and any other design factor — not only as a single aggregate number — so that uniformity of agreement across the domain can be distinguished from agreement driven by a tractable subset. *(Sprouse & Almeida 2012; Sprouse, Schütze & Almeida 2013; Barr et al. 2013)*

  > **Implementation status: full.** The pre-existing `infereval metrics --by-tag` and `--by-rsr-target` flags provided basic decomposition. Deepened in v0.4.1 (Issue #40) by `infereval model`, which fits a logistic regression of agreement on declared factors with per-factor joint Wald tests — converting per-cell kappa values into proper structural characterizations ("main effect of side-premise type, p < 0.001; no main effect of paraphrase variant").

**Requirements on the form of mastery claims**

- **R16. Explicit specification of the mastery sense intended.** The methodology must state whether the mastery claim is about evaluative behavior (endorsements-when-asked), generative behavior, standing competence, or some combination, and must restrict its claims to the sense the measurement supports. *(Allen 2026 Remark 7; Brandom 1994)*

  > **Implementation status: full.** Shipped in v0.5.0 (Issue #44) as `ConstructValidityClaims.mastery_sense`, a required claims-file field with a `Literal["evaluative", "generative", "standing", "combination"]` discriminator + required free-text description. The `infereval report` command refuses to render without this field populated.

- **R17. Explicit specification of the scope of the claim.** The methodology must state whether the mastery claim is about (a) the items in β, (b) the domain D as sampled by β, or (c) inferential mastery as a general capacity, and must provide arguments appropriate to the scope claimed. *(Messick 1989; Allen 2026 Remark 9)*

  > **Implementation status: full.** Shipped in v0.5.0 (Issue #44) as `ConstructValidityClaims.scope`, with a `Literal["items_in_benchmark", "domain_D_as_sampled", "general_capacity"]` discriminator and a tiered set of required competing-explanation checks per scope. Broader scopes require strictly more checks; the verdict downgrades automatically when checks are missing.

**Requirements on reporting**

- **R20. Disclosure of all analyst-supplied choices.** The methodology must report B, δ, ctx_Γ, ctx_Δ, the verification prompt, the analyst pool composition, the construction procedure for β, the sampling and aggregation choices for E_M, and any other free parameters, so that the measurement is reproducible and the carving is visible to anyone evaluating the mastery claim. *(Mitchell et al. 2019; Gebru et al. 2021; Pineau et al. 2021)*

  > **Implementation status: full.** The benchmark and evaluation JSON schemas already carried B, δ, the context builders, the verification prompt, and the analyst panel. Extended with `construction_metadata` (R5, v0.3.2), `references` (#18, v0.2.2), and `paraphrase_variant` on the Evaluation (R10, v0.3.1). `infereval describe` surfaces every declared choice; the construct-validity report (v0.5.0) lists them as the disclosed methodology section.

### Tier 2: necessary for a defensible mastery claim

**Requirements on the analyst pool and reference standard**

- **R4. Independent reference check.** The methodology must include, at least once per benchmark, a comparison of agreement results against an independent reference source (a second analyst panel, an authoritative external benchmark, or domain-recognized credentialing) to guard against shared-error agreement among the primary analyst pool. *(Campbell & Fiske 1959; Cronbach & Meehl 1955)*

  > **Implementation status: full (tooling); partial (operational).** Shipped in v0.3.3 (Issue #36): `AnalystModel.panel` + `Benchmark.primary_panel` declare multiple panels; new `inter_analyst_fleiss_per_panel` and `cross_panel_kappa` metrics compute per-panel κ_F* and Cohen's κ between two panels' per-item consensus columns. The framework now *handles* the independent reference check end-to-end once two panels exist. **Recruiting a second panel remains a workflow responsibility** — see "What only a research program can do" below.

**Requirements on benchmark construction**

- **R8. Held-out items constructed independently of M.** The methodology must include items constructed without reference to M's outputs or behavior, ideally by analysts who haven't observed M, to prevent the benchmark from being implicitly tailored to the model under evaluation. *(Sainz et al. 2023; Pineau et al. 2021)*

  > **Implementation status: partial.** The `construction_metadata.authored_blind_to_models` field (v0.3.2, Issue #34) lets each item declare which models the author had not observed at authoring time. The construct-validity report's competing-explanation checks include `held_out_items_used` as a tracked declaration. **The institutional separation between benchmark authors and model evaluators remains a research-program responsibility.**

- **R9. Training-data separation.** The methodology must include checks or controls — temporal (β constructed after training cutoff), structural (no verbatim or near-duplicate matches against training data), or both — sufficient to rule out memorization as an alternative explanation for agreement. *(Sainz et al. 2023)*

  > **Implementation status: partial.** The `construction_metadata.authored_on` field (v0.3.2) records the authoring date so temporal separation can be argued. The construct-validity report tracks `training_data_separation_verified` as a declared check. **Verifying actual training-data overlap requires model-provider cooperation or external tooling outside infereval's scope.**

**Requirements on stimulus design**

- **R11. Sensitivity analysis on free parameters.** The methodology must report agreement results under variation of analyst-supplied methodological choices — verification prompt wording, expression-function choices, sample size for majority voting, aggregation rule — so that robustness of agreement to these choices is established rather than assumed. *(Sclar et al. 2024; Lu et al. 2022)*

  > **Implementation status: full.** Shipped in v0.4.2 (Issue #42). New `infereval sweep` command sweeps over `n_samples`, `tie_break`, `paraphrase_variant`, or `temperature`. Per-value evaluation artifacts + aggregate `sweep-summary.json`. The `SweepResult.stability_verdict` deterministically classifies the κ_C range into stable / moderately sensitive / substantively variable, with escalating language so unstable sweeps tell the reader to consider tighter choices.

**Requirements on the analysis**

- **R13. Structural coherence check on the derived frame.** The methodology must include a post-evaluation check that ⟨B, I_M⟩ exhibits the structural properties the inferentialist framework treats as constitutive of mastery (closure under containment, coherent RSR behavior, appropriate defeasibility patterns), so that aggregate agreement isn't conflated with structural mastery. *(Hlobil & Brandom 2025; Brandom 1994; Allen 2026 Remark 5)*

  > **Implementation status: full.** Shipped in v0.4.0 (Issue #38) — *the philosophically central addition*. New `infereval.structure` module with three checks: `containment_closure_check`, `rsr_role_consistency_check`, `base_case_stability_check`. New `infereval structure <eta.json> --benchmark <bench>` CLI command produces a human-readable report flagging per-item anomalies. Live integration against the bundled pulmonology data correctly surfaces the a9 anomaly we'd been flagging by hand all along.

- **R14. Cross-domain comparison.** The methodology must include evaluation of M on benchmarks in at least one comparison domain D′, so that domain-specific competence can be distinguished from general capability that happens to apply to D. *(Campbell & Fiske 1959; Cronbach & Meehl 1955)*

  > **Implementation status: not addressed by the framework — research-program responsibility.** The framework supports running M against any benchmark; producing the comparison is the analyst's work. The construct-validity report tracks `cross_domain_comparison_run` as a declared check and downgrades the verdict when it's missing at `scope=general_capacity`.

**Requirements on the form of mastery claims**

- **R18. Explicit position on the constitution-versus-evidence question.** The methodology must state whether agreement is being treated as evidence of mastery (a deeper property) or as partially constitutive of mastery (the framework's structural-behavioral characterization), so that the weight assigned to the agreement statistic is calibrated to the philosophical commitment being made. *(Brandom 1994; Hlobil & Brandom 2025; Simonelli 2026)*

  > **Implementation status: full.** Shipped in v0.5.0 (Issue #44) as `ConstructValidityClaims.constitution`, with a `Literal["evidence_of_mastery", "constitutive_of_mastery"]` discriminator and required justification. The position is rendered verbatim in the report under section 3 (Construct-validity claims).

**Requirements on reporting**

- **R21. Disclosure of failed checks and negative results.** The methodology must report results of paraphrase sensitivity, cross-domain comparison, structural coherence checks, and replication attempts even when they fail to support the mastery claim, so that the evidence is presented complete rather than selectively. *(Munafò et al. 2017; Pineau et al. 2021)*

  > **Implementation status: full.** Shipped in v0.5.1 (Issue #46). `collect_negative_findings()` scans the structure / sweep / model-fit artifacts for findings that weaken the mastery claim and surfaces them in a dedicated Section 4b of the report. `--suppress-negatives` is the explicit opt-out: it (1) replaces the body with a suppression banner naming the flag, (2) adds a `Negative-findings suppression: ENABLED` warning to the report header, and (3) downgrades the Summary verdict one tier. The asymmetry — cheap to surface failures, expensive to suppress them — works at three levels at once.

### Tier 3: necessary for a strong mastery claim

**Requirements on the analysis**

- **R15. Replication.** The methodology must specify replication conditions — fresh sampling from M, comparable analyst pools, freshly constructed benchmarks following the same construction procedure — and report whether the agreement results replicate under those conditions. *(Open Science Collaboration 2015; Munafò et al. 2017; Pineau et al. 2021)*

  > **Implementation status: partial — workflow piece, supported by the artifact infrastructure.** Strict reproducibility (same benchmark, same params, fresh provider call) is already covered by the SHA-256 hash + immutable JSON artifact infrastructure. Replication in the scientific sense (fresh analyst panel, freshly constructed benchmark, same procedure) is a research-program responsibility. The construct-validity report tracks `replication_attempted` as a declared check.

**Requirements on the form of mastery claims**

- **R19. Carving-indexed framing of in-principle claims.** The methodology must frame any in-principle claims about mastery in the carving-indexed form Remark 9 specifies, rather than as unrestricted claims about concept possession, so that the relativity to analyst-supplied carving is preserved in what gets concluded from the measurement. *(Allen 2026 Remark 9; Simonelli 2026; Hlobil & Brandom 2025)*

  > **Implementation status: full at the report level.** Shipped in v0.5.0 (Issue #44) as `ConstructValidityClaims.carving`, with `acknowledges_carving_indexed: bool` + `notes: str`. The verdict computation requires both `acknowledges_carving_indexed=True` AND non-empty `notes` when the claim's scope reaches beyond `items_in_benchmark` (i.e. when in-principle claims are being made). Failing either condition automatically downgrades the verdict to NOT defensible. The framework can't enforce carving-indexed framing in third-party write-ups but can refuse to render a defensible verdict for write-ups that ignore it.

## The shape of the gap

The construct-validity requirements divide into two groups:

- **Workflow requirements** that no tool can substitute for: recruiting independent analyst panels, organizing separation-of-duties between benchmark construction and model evaluation, generating cross-domain studies, writing up results in appropriately scoped terms.
- **Infrastructure requirements** that the framework could make tractable: factorial design support, paraphrase-axis automation, provenance metadata, structural coherence checks, sensitivity analysis sweeps, construct-validity reporting templates.

The recommendations below focus on the second group. They are organized into three phases corresponding roughly to (1) making structure visible, (2) checking structure rigorously, and (3) disciplining claims made from the structure.

## What only a research program can do

Six requirements are workflow discipline that the framework can support but not replace:

**Independent reference panels.** Someone has to recruit a second analyst pool with independent training, label the same benchmark, and compare. The framework can make the comparison machinery easy; it can't recruit the panel.

> **Implementation note.** As of v0.3.3 the comparison machinery is fully built (`cross_panel_kappa`, `inter_analyst_fleiss_per_panel`, the panel section of `infereval describe`). What remains is the institutional work.

**Held-out items constructed independently of M.** This requires institutional separation between benchmark authors and model evaluators, with authors blind to the model's outputs. The framework can record authorship metadata; the discipline itself is institutional.

> **Implementation note.** As of v0.3.2 the framework records `authored_by`, `authored_on`, `authored_blind_to_models`, and `source` per item. The construct-validity report (v0.5.0) tracks `held_out_items_used` as a declared check.

**Training-data separation.** Partly addressable through temporal metadata (constructed-after dates); deeper separation requires either model-provider cooperation or external tooling outside infereval's scope.

> **Implementation note.** Temporal metadata lives in `construction_metadata.authored_on`. Deeper separation work is still external.

**Scientific replication.** Strict reproducibility is already provided by the SHA-256 hash and audit log infrastructure. Replication in the scientific sense — fresh analyst panels, fresh benchmarks, same construction procedure — requires additional studies the framework can lower the cost of but cannot substitute for.

> **Implementation note.** The construct-validity report tracks `replication_attempted` as a declared check.

**Mastery-sense, scope, and constitution-versus-evidence claims.** These are interpretive commitments by whoever writes up results. The framework can prompt for explicit statements but cannot supply the substance.

> **Implementation note.** As of v0.5.0 the framework *requires* explicit statements via the claims file. It cannot supply the substance but it can refuse to render strong verdicts without them.

**Carving-indexed framing of in-principle claims.** The framing comes from the analyst's understanding of the paper's Remark 9; the framework can carry the framing forward in its documentation but cannot enforce its use in third-party write-ups.

> **Implementation note.** As of v0.5.0 the framework can at least refuse to render a `defensible` verdict for claims that reach beyond `items_in_benchmark` without an acknowledged + documented carving. The mechanic protects the framework's own output; what downstream readers do with the rendered report is still up to them.

The right response to these is to organize the research community to do the work, not to extend the tool to pretend otherwise.

## Phase 1: Schema and metadata extensions

These are additive schema changes that don't break existing benchmarks. They give Tier 1 requirements immediate support and lay the foundation for Phase 2's analytical extensions. Most of the work here is design — getting the schema right — rather than implementation.

> **Shipped as v0.3.0 / v0.3.1 / v0.3.2 / v0.3.3** (Issues #30 / #32 / #34 / #36). Four releases, ~1500 lines of code + tests + docs. Backwards-compatible additive schema additions — `schema_version` stays `"1.0"` throughout.

### Factorial-design metadata

**Addresses:** R7 (multiple items per condition), supports R12 (per-condition decomposition).

Add a `factors` field at the benchmark level declaring which design factors are in play and which levels each has, and a `factor_levels` field on each item recording its position in the design space. Validators check that every cell of the crossed design contains at least k items, with k parameterized by the analyst.

```json
"factors": {
  "side_premise_type": ["none", "irrelevant", "perceptual_defeater", "genuine_defeater"],
  "target_inference": ["color", "shape", "function"],
  "paraphrase_variant": ["v1", "v2", "v3"]
},
"factor_constraints": {"min_items_per_cell": 3}
```

The validator complains if a cell is underpopulated. This converts the current bag-of-items benchmark into a structured design without breaking backward compatibility — unstructured benchmarks just have no factors declared.

> **Shipped as v0.3.0 (Issue #30, PR #31).** New Pydantic types `FactorConstraints` + the `factors` / `factor_constraints` / `factor_levels` fields. Validation rejects items with unknown factor keys or unknown level values, and rejects under-populated designs with an error message listing the underpopulated cells. New helpers `Benchmark.cells()` and `Benchmark.is_fully_crossed_at_k(k)`. `infereval describe` gains a `factorial design:` section. 15 new tests.

### Runtime paraphrase-axis support

**Addresses:** R10 (paraphrase variation under fixed inferential content).

Promote the existing `paraphrases` field on bearers from documentation-only to runtime-active. A new flag `--paraphrase-cycle` issues the verification prompt against multiple paraphrases per item and reports per-paraphrase verdicts, with kappa decomposable by paraphrase variant. This is what `experiments/paraphrase_axis_triangulation.py` does by hand; built-in support makes paraphrase robustness analysis a one-flag operation.

> **Shipped as v0.3.1 (Issue #32, PR #33).** `_expressions_for(..., variant=k)` threads the variant through the prompt pipeline. `endorse(...)` and `evaluate(...)` accept `variant=k`; new `Evaluation.paraphrase_variant` field; new `Benchmark.n_paraphrase_variants` helper. CLI: `--paraphrase-variant K` and `--paraphrase-cycle` on `infereval evaluate`, mutually exclusive, with cycle suffixing the output / log / run-id paths with `-vN`. 20 new tests.

### Construction-provenance metadata

**Addresses:** R5 (documented construction), R8 (held-out items), R9 (training-data separation).

Add fields recording who authored each item, when, with what source materials, and against what training-cutoff dates. The framework validates that the fields are present and parse correctly; their content is the analyst's responsibility but their presence becomes auditable.

```json
"construction_metadata": {
  "authored_by": "physician-c",
  "authored_on": "2026-04-15",
  "authored_blind_to_models": ["claude-opus-4-7", "gpt-5"],
  "source": "Sanford Guide to Antimicrobial Therapy 2025"
}
```

> **Shipped as v0.3.2 (Issue #34, PR #35).** New `ConstructionMetadata` Pydantic model with `authored_by` / `authored_on` (ISO date) / `authored_blind_to_models` / `source` fields. Pydantic's `extra="forbid"` rejects unknown sub-fields. `infereval describe` gains a `construction provenance:` summary section + a per-item `construction:` line under `--items`. 10 new tests.

### Reference-panel declaration

**Addresses:** R4 (independent reference check).

Support multiple analyst panels per benchmark, with a flag indicating which is primary and which is for independent-check use. `κ_F*` becomes computable per panel, plus a cross-panel agreement statistic that surfaces when the panels diverge.

> **Shipped as v0.3.3 (Issue #36, PR #37).** `AnalystModel.panel` + `Benchmark.primary_panel` fields. Validation rejects partial-panel benchmarks (some analysts have panels, others don't) and rejects `primary_panel` values that don't name an actual panel. New metrics `inter_analyst_fleiss_per_panel` and `cross_panel_kappa`. `infereval describe` gains an `analyst panels:` section with per-panel κ_F* + cross-panel κ_C. 14 new tests. **Closes Phase 1.**

## Phase 2: Analytical extensions

These build on the Phase 1 schema changes and require more implementation work — wrapping statistical libraries, implementing structural checks against ⟨B, I_M⟩, orchestrating multi-run sweeps. The payoff is moving the framework's analytical surface from kappa-and-decompositions to something closer to the structural characterizations the inferentialist framework actually motivates.

> **Shipped as v0.4.0 / v0.4.1 / v0.4.2** (Issues #38 / #40 / #42). Three releases including the first new optional dependency (`statsmodels` under `[stats]`).

### Mixed-effects model fitting

**Addresses:** R7, R12, deepens the per-condition decomposition.

Beyond the current per-tag decompositions, a `infereval model` command fits a generalized linear mixed-effects model with M's verdict as the outcome, declared factors as fixed effects, and items and analysts as random effects. The output is the kind of structural characterization R12 actually wants: main effects, interactions, variance components — "main effect of side-premise type, p < 0.001; no main effect of paraphrase variant; no significant interaction" rather than just per-cell kappa values.

This is standard analytical machinery (lme4-equivalent in Python via bambi or pymer4), wrappable as a CLI command on top of Phase 1's factorial-design metadata.

> **Shipped as v0.4.1 (Issue #40, PR #41) with a scope decision.** Rather than adding bambi/PyMC (~50 MB install + heavy compile), this release ships **fixed-effects logistic regression with item-clustered standard errors via `statsmodels`** as a proxy for the per-item random-effect structure. The CLI/module/CHANGELOG all explicitly call out the caveat; the marginal fixed-effects coefficients and joint Wald tests (which is what the document's "main effect of side-premise type, p < 0.001" output most directly needs) are recoverable. Variance-component decomposition is the only piece sacrificed. A follow-up issue can swap to bambi for projects that need the full GLMM treatment. 8 new tests.

### Structural coherence checks on ⟨B, I_M⟩

**Addresses:** R13 (structural coherence check on the derived frame).

Implement built-in checks for the structural properties the Hlobil–Brandom framework treats as constitutive of mastery: closure under containment (already guaranteed by construction), coherent RSR behavior for declared target inferences, monotonicity where expected, defeater symmetry, and others the framework specifies. A `infereval structure` command runs these checks against the derived frame and reports which structural properties hold, which fail, and which are inconclusive given the benchmark's coverage.

This converts the current situation — frame is available as an object, structural checks are left to the analyst — into one where the structural checks the framework explicitly motivates are themselves first-class operations.

> **Shipped as v0.4.0 (Issue #38, PR #39).** New `infereval.structure` module with three checks: `containment_closure_check` (sanity-counts self-implications), `rsr_role_consistency_check` (compares role-tagged items' verdicts against the role's prediction from the base verdict), `base_case_stability_check` (multi-base targets agree). New CLI `infereval structure <eta.json> --benchmark <bench>`. 16 new tests — the CLI integration against the bundled pulmonology artifacts correctly surfaces the a9 anomaly that earlier hand-analysis had flagged. **This is the philosophically central addition** — the structural checks the inferentialist framework explicitly motivates are now first-class operations.

### Sensitivity-analysis sweeps

**Addresses:** R11 (sensitivity analysis on free parameters).

A `infereval sweep` command runs the same benchmark under varied verification prompts, varied δ choices, varied sample sizes, and varied aggregation rules, then reports how stable the agreement statistics are across the sweep. The reproducibility infrastructure (immutable artifacts, SHA-256 hashing) is already in place; the sweep is orchestration on top of it.

> **Shipped as v0.4.2 (Issue #42, PR #43).** New `infereval.sweep` module + CLI command. Supported sweep parameters: `n_samples`, `tie_break`, `paraphrase_variant`, `temperature`. Per-value evaluation + JSONL log artifacts plus aggregate `sweep-summary.json`. `SweepResult.stability_verdict` classifies κ_C range into stable (< 0.05) / moderately sensitive (< 0.10) / substantively variable (≥ 0.10) with escalating language. 18 new tests. **Closes Phase 2.**

## Phase 3: Reporting and methodological discipline

This is where the framework starts taking positions about how its output should be used. That's appropriate at this stage but would be premature before the analytical extensions are in place.

> **Shipped as v0.5.0 / v0.5.1** (Issues #44 / #46). Two releases; the 0.x.y minor bump marks the Phase-2-to-Phase-3 transition.

### Construct-validity report

**Addresses:** R16 (mastery sense), R17 (scope), R18 (constitution vs evidence), R19 (carving-indexed framing), R20 (disclosure), R21 (negative results).

A `infereval report` command produces a structured write-up combining the metrics with prompts for the analyst to fill in: the mastery sense being claimed, the scope, the position on constitution-vs-evidence, the carving-relative framing of any in-principle claims, and explicit acknowledgment of which competing-explanation checks were and weren't run. The report has slots; the analyst fills them; the framework refuses to render a "mastery established" headline without the slots being filled.

This is the most opinionated of the proposed extensions. It embeds a methodological position about what claims should be made on top of what evidence. That commitment is appropriate given that the gap being closed is exactly the gap between measurement and warranted claim.

> **Shipped as v0.5.0 (Issue #44, PR #45).** New `infereval.report` module with `ConstructValidityClaims` Pydantic model carrying `mastery_sense` (R16), `scope` (R17), `constitution` (R18), `carving` (R19), and `competing_explanations` (R4 / R8 / R9 / R11 / R13 / R14 / R15). Deterministic `compute_verdict()`: `defensible` / `partially_defensible` / `not_defensible` based on the claimed scope's required-checks set. **The verdict refuses to render `defensible` without the corresponding checks** — and at `scope=general_capacity` requires both `acknowledges_carving_indexed=True` AND non-empty `notes` (R19 enforcement). New CLI `infereval report` with `--init-claims` (write stub), `--evaluation` / `--benchmark` / `--claims` (render full report), and `--structure` / `--sweep` / `--model-fit` (auto-integrate Phase 2 artifacts). 19 new tests.

### Negative-results aggregation

**Addresses:** R21 (disclosure of failed checks and negative results).

When the analyst runs paraphrase sweeps, structural checks, or sensitivity analyses, the framework collects the negative findings alongside the positive ones and includes them in the report by default. Suppression requires an explicit flag, which is itself documented in the output. The asymmetry — easy to report failures, harder to hide them — is the construct-validity infrastructure working at the reporting level.

> **Shipped as v0.5.1 (Issue #46, PR #47).** `collect_negative_findings()` auto-scans the three Phase 2 artifacts (structure report, sweep summary, model fit) for findings that weaken the mastery claim. New Section 4b "Negative findings" in the report. `--suppress-negatives` is the explicit opt-out with three asymmetric side-effects: (1) section body replaced by a suppression banner naming the flag, (2) `Negative-findings suppression: ENABLED` warning added to the report header, (3) Summary verdict downgrades one tier. 13 new tests. **Closes Phase 3 and the entire construct-validity infrastructure series.**

## What remains irreducibly outside the framework

Even after all three phases, several things remain workflow rather than tooling:

- Recruiting independent analyst pools
- Organizing separation-of-duties between benchmark construction and model evaluation
- Generating cross-domain studies
- Writing up results in carving-indexed terms (in third-party text the framework can't see)
- Resolving the philosophical commitments around mastery and concept-possession

These are research-program responsibilities. The right framework posture is to make them easy and visible rather than to pretend to substitute for them.

> **Implementation posture.** Every workflow requirement has *infrastructure* that makes the work cheaper and *declarations* that make its presence/absence visible in the report. Recruiting a second panel is still recruitment work; using it once recruited is a one-line schema change. Producing a cross-domain study is still study work; declaring whether one was produced is a single boolean in the claims file.

## Coverage after the extensions

| Requirement | Current (pre-0.3) | After Phase 1 (0.3.x) | After Phase 2 (0.4.x) | After Phase 3 (0.5.x) |
|---|---|---|---|---|
| R1 documented analyst competence | Partial | Partial | Partial | Partial |
| R2 inter-analyst baseline | Full | Full | Full | Full |
| R3 baseline-relative framing | Full | Full | Full | Full |
| R4 independent reference | Not addressed | **Full (tooling)** | Full | Full |
| R5 documented construction | Partial | **Full** | Full | Full |
| R6 inferential-type coverage | Partial | **Full** | Full | Full |
| R7 multiple items per condition | Not addressed | **Full** | Full | Full |
| R8 held-out items | Not addressed | **Partial** (metadata) | Partial | Partial |
| R9 training-data separation | Not addressed | **Partial** (temporal) | Partial | Partial |
| R10 paraphrase variation | Partial | **Full** | Full | Full |
| R11 sensitivity analysis | Partial | Partial | **Full** | Full |
| R12 per-condition decomposition | Full | Full | **Deepened** | Full |
| R13 structural coherence check | Partial | Partial | **Full** | Full |
| R14 cross-domain comparison | Not addressed | Not addressed | Not addressed | Tracked (not run) |
| R15 replication | Partial | Partial | Partial | Tracked (not run) |
| R16 mastery sense | Not addressed | Not addressed | Not addressed | **Full** |
| R17 claim scope | Not addressed | Not addressed | Not addressed | **Full** |
| R18 constitution vs evidence | Not addressed | Not addressed | Not addressed | **Full** |
| R19 carving-indexed claims | Partial | Partial | Partial | **Full** (at report level) |
| R20 disclosure of choices | Full | Full | Full | Full |
| R21 negative-results disclosure | Partial | Partial | Partial | **Full** |

(**Bold** marks the cells that changed in each phase column.)

Three observations from the as-shipped table.

First, **Phase 1 closes the largest number of gaps because so much of construct validity is about *making structure visible*** — declaring design factors, recording provenance, supporting paraphrase variation, separating reference panels. These are schema changes that have outsized impact.

Second, **Phases 2 and 3 close fewer cells but the cells they close are the ones that matter most philosophically.** Structural coherence checks (R13, v0.4.0) and the interpretive requirements (R16–R19, v0.5.0–v0.5.1) are where the framework moves from supporting agreement measurement to supporting mastery characterization in the inferentialist sense.

Third, **R8, R9, R14, and R15 remain partial or tracked-not-run after all three phases.** These are the requirements that genuinely require external resources — independent annotators, training-corpus access, cross-domain studies, fresh replication studies — and the framework's right posture is to make them tractable rather than to claim to provide them. The construct-validity report tracks each as a declared boolean and downgrades the verdict when they're false at the wrong scope.

## The disposition the extensions embody

The framework's job, on the proposal here, is to make the construct-validity work *cheap enough to do* and *expensive enough to skip*. The extensions move in both directions: cheaper because the infrastructure handles the bookkeeping (factorial validation, paraphrase cycling, structural checks, report generation); more expensive to skip because skipping requires explicitly opting out of checks the framework otherwise runs by default.

The research program still has to do the studies. The framework can make it harder to publish a mastery claim without them. That's the right place for a measurement tool to land — taking construct validity seriously without pretending to settle it, which is more or less the disposition the current concepts documentation already articulates, extended into the parts of the workflow that currently sit outside the framework's scope.

> **As shipped, the asymmetry plays out in three concrete places**:
>
> 1. **Validation refuses bad designs.** The factorial-design validator rejects under-populated benchmarks; the panel validator rejects partial-panel benchmarks; the claims file rejects missing required fields.
> 2. **Reports refuse strong claims without evidence.** The construct-validity report deterministically downgrades the verdict when required checks are missing; at `scope=general_capacity` it requires acknowledged + documented carving (R19) or auto-downgrades to NOT defensible regardless of how many checks ran.
> 3. **Suppression is visible.** `--suppress-negatives` documents itself in the report header AND downgrades the verdict one tier. Hiding evidence is itself flagged as a negative construct-validity signal.

## Recommended sequencing

If only some of the proposed extensions can be implemented, the priority order is:

1. **Factorial-design metadata and runtime paraphrase support.** These are the schema changes with the largest interpretive payoff per unit of implementation effort. Paraphrase support in particular addresses the single most-cited concern about content-vs-form sensitivity.
2. **Construction-provenance metadata.** Cheap to add, high audit value, foundation for later separation-of-duties workflows.
3. **Structural coherence checks.** The philosophically central addition — converts the framework from agreement measurement to mastery characterization in the framework's own structural sense.
4. **Mixed-effects model fitting and sensitivity sweeps.** Important but tractable as third-party extensions if not built in.
5. **Construct-validity report and negative-results aggregation.** Most opinionated; should follow rather than precede the analytical machinery they would report on.

Reference-panel declaration sits at priority 2 or 3 depending on whether independent-panel studies are already in the framework's near-term research roadmap.

> **As shipped.** The implementation followed the recommended sequencing exactly. Reference-panel declaration landed at the end of Phase 1 (priority 4 within Phase 1, after the other three pieces) since the cross-panel metrics depend on the schema being in place first. Each phase shipped sequentially across releases v0.3.0 → v0.5.1, eleven releases in total.

## What was shipped, end to end

A condensed view of the entire programme:

| Phase | Version | Issue | Feature | Requirements addressed |
|---|---|---|---|---|
| **1.1** | v0.3.0 | #30 | factorial-design metadata | R7, R12 |
| **1.2** | v0.3.1 | #32 | runtime paraphrase-axis support | R10 |
| **1.3** | v0.3.2 | #34 | construction-provenance metadata | R5, R8, R9 |
| **1.4** | v0.3.3 | #36 | reference-panel declaration + cross-panel κ | R4 |
| **2.1** | v0.4.0 | #38 | structural coherence checks | R13 |
| **2.2** | v0.4.1 | #40 | factor-effects model fitting | R7, R12 |
| **2.3** | v0.4.2 | #42 | sensitivity-analysis sweeps | R11 |
| **3.1** | v0.5.0 | #44 | construct-validity report | R16–R20 |
| **3.2** | v0.5.1 | #46 | negative-results aggregation | R21 |

Total: nine features shipped across nine PRs, all rebase-merged into `main`. ~150 new tests across the programme, ruff & mypy clean at every release. Eleven releases, eleven GitHub Releases with wheel + sdist attached.

The framework that exists at the end of this programme is recognizably continuous with the one that existed before it — every change was additive and backwards-compatible at the JSON-schema level — but it now does what *Closing the Construct-Validity Gap in infereval* asked it to do. The next step is using the tooling, which is what the companion document [`construct_validity_workflow.md`](construct_validity_workflow.md) is for.

## References

Allen, B. P. (2026). Note on Simonelli's Stop Sign Dialogue: An Implication-Space Methodology for the Empirical Evaluation of LLM Inferential Mastery.

Baayen, R. H., Davidson, D. J., & Bates, D. M. (2008). Mixed-effects modeling with crossed random effects for subjects and items. *Journal of Memory and Language*, 59(4), 390–412.

Barr, D. J., Levy, R., Scheepers, C., & Tily, H. J. (2013). Random effects structure for confirmatory hypothesis testing: Keep it maximal. *Journal of Memory and Language*, 68(3), 255–278.

Bender, E. M., & Friedman, B. (2018). Data statements for natural language processing: Toward mitigating system bias and enabling better science. *Transactions of the Association for Computational Linguistics*, 6, 587–604.

Brandom, R. B. (1994). *Making It Explicit: Reasoning, Representing, and Discursive Commitment*. Harvard University Press.

Campbell, D. T., & Fiske, D. W. (1959). Convergent and discriminant validation by the multitrait-multimethod matrix. *Psychological Bulletin*, 56(2), 81–105.

Cowart, W. (1997). *Experimental Syntax: Applying Objective Methods to Sentence Judgments*. Sage.

Cronbach, L. J., & Meehl, P. E. (1955). Construct validity in psychological tests. *Psychological Bulletin*, 52(4), 281–302.

Fleiss, J. L. (1971). Measuring nominal scale agreement among many raters. *Psychological Bulletin*, 76(5), 378–382.

Gebru, T., Morgenstern, J., Vecchione, B., Vaughan, J. W., Wallach, H., Daumé III, H., & Crawford, K. (2021). Datasheets for datasets. *Communications of the ACM*, 64(12), 86–92.

Hlobil, U., & Brandom, R. B. (2025). *Reasons for Logic, Logic for Reasons*. Routledge.

Landis, J. R., & Koch, G. G. (1977). The measurement of observer agreement for categorical data. *Biometrics*, 33(1), 159–174.

Lu, Y., Bartolo, M., Moore, A., Riedel, S., & Stenetorp, P. (2022). Fantastically ordered prompts and where to find them. *ACL 2022*.

McCoy, R. T., Pavlick, E., & Linzen, T. (2019). Right for the wrong reasons: Diagnosing syntactic heuristics in natural language inference. *ACL 2019*.

Messick, S. (1989). Validity. In R. L. Linn (Ed.), *Educational Measurement* (3rd ed., pp. 13–103). American Council on Education.

Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). Model cards for model reporting. *FAT\* 2019*.

Munafò, M. R., et al. (2017). A manifesto for reproducible science. *Nature Human Behaviour*, 1, 0021.

Open Science Collaboration. (2015). Estimating the reproducibility of psychological science. *Science*, 349(6251).

Pineau, J., et al. (2021). Improving reproducibility in machine learning research. *JMLR* 22(164).

Ribeiro, M. T., Wu, T., Guestrin, C., & Singh, S. (2020). Beyond accuracy: Behavioral testing of NLP models with CheckList. *ACL 2020*.

Sainz, O., Campos, J. A., García-Ferrero, I., Etxaniz, J., de Lacalle, O. L., & Agirre, E. (2023). NLP evaluation in trouble. *EMNLP 2023*.

Schütze, C. T. (1996/2016). *The Empirical Base of Linguistics*. Language Science Press.

Sclar, M., Choi, Y., Tsvetkov, Y., & Suhr, A. (2024). Quantifying language models' sensitivity to spurious features in prompt design. *ICLR 2024*.

Simonelli, R. (2026). Sapience without sentience. *Asian Journal of Philosophy*, 5(1).

Sprouse, J., & Almeida, D. (2012). Assessing the reliability of textbook data in syntax. *Journal of Linguistics*, 48(3).

Sprouse, J., Schütze, C. T., & Almeida, D. (2013). A comparison of informal and formal acceptability judgments. *Lingua*, 134.
