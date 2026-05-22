"""Construct-validity report — the most opinionated extension in the series.

Phase 3.1 of the construct-validity infrastructure (per *Closing the
Construct-Validity Gap in infereval*). Closes R16 (mastery sense),
R17 (scope), R18 (constitution vs. evidence), R19 (carving-indexed
framing), and R20 (disclosure of analyst-supplied choices).

The asymmetry this module embodies: **cheap to write up correctly,
expensive to write up incorrectly**. The slot structure makes it
impossible to publish a "mastery established" summary verdict without
the corresponding analyst declarations and competing-explanation
checks. The framework refuses to render the strong-form header
without the supporting evidence; the analyst is welcome to publish
weak claims with the appropriate hedge but cannot publish them with
the unmarked banner.

The report integrates a fixed set of *analyst declarations* (the
:class:`ConstructValidityClaims` model) with auto-collected evidence
from optional Phase 2 artifacts (structural-coherence report, sweep
summary, factor-effects model fit). The summary verdict is computed
deterministically against the claims + evidence, not by the analyst.

The output is structured Markdown — readable as text, version-
controllable, and viewable as a rendered page.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .benchmark import Benchmark
    from .evaluation import Evaluation


# ---- Claims schema --------------------------------------------------------


class MasterySenseClaim(BaseModel):
    """R16: which sense of mastery the claim is about."""

    model_config = ConfigDict(extra="forbid")

    sense: Literal["evaluative", "generative", "standing", "combination"]
    """- ``evaluative``: endorsements-when-asked (the methodology's direct measurement).
    - ``generative``: inferential behavior in unprompted production.
    - ``standing``: a dispositional competence underlying both.
    - ``combination``: a mix; describe explicitly in ``description``."""
    description: str
    """One to three sentences, the analyst's own articulation."""


class ScopeClaim(BaseModel):
    """R17: scope the mastery claim applies over."""

    model_config = ConfigDict(extra="forbid")

    scope: Literal["items_in_benchmark", "domain_D_as_sampled", "general_capacity"]
    """- ``items_in_benchmark``: the claim is about the specific items in β.
    - ``domain_D_as_sampled``: the claim generalises to D as sampled by β.
    - ``general_capacity``: the claim is about inferential mastery as a general capacity."""
    justification: str
    """Why this scope is appropriate given β and the methodology used."""


class ConstitutionClaim(BaseModel):
    """R18: is agreement *evidence of* mastery or *constitutive of* it?"""

    model_config = ConfigDict(extra="forbid")

    position: Literal["evidence_of_mastery", "constitutive_of_mastery"]
    """- ``evidence_of_mastery``: agreement is evidence for a deeper underlying property.
    - ``constitutive_of_mastery``: agreement (with structural coherence) IS mastery (Brandom's structural-behavioural characterisation)."""
    justification: str
    """Brief explanation of the position taken and why."""


class CarvingClaim(BaseModel):
    """R19: carving-indexed framing of in-principle claims."""

    model_config = ConfigDict(extra="forbid")

    acknowledges_carving_indexed: bool
    """``True`` iff any in-principle claims are framed in the
    carving-indexed form Remark 10 specifies."""
    notes: str = ""
    """Required when ``acknowledges_carving_indexed`` is ``True``;
    document the carving used or pointers to the discussion."""


class CompetingExplanationChecks(BaseModel):
    """R4, R8, R9, R11, R13, R14, R15: which checks were actually run.

    All fields default to ``False`` (the conservative posture — the
    framework assumes no check was done unless the analyst explicitly
    declares it). The report's *Unaddressed competing explanations*
    section lists every ``False``.
    """

    model_config = ConfigDict(extra="forbid")

    paraphrase_sweep_run: bool = False
    sensitivity_sweep_run: bool = False
    structural_check_run: bool = False
    cross_panel_check_run: bool = False
    independent_reference_panel_used: bool = False
    held_out_items_used: bool = False
    training_data_separation_verified: bool = False
    cross_domain_comparison_run: bool = False
    replication_attempted: bool = False


class ConstructValidityClaims(BaseModel):
    """Top-level container for the analyst's construct-validity declarations."""

    model_config = ConfigDict(extra="forbid")

    mastery_sense: MasterySenseClaim
    scope: ScopeClaim
    constitution: ConstitutionClaim
    carving: CarvingClaim
    competing_explanations: CompetingExplanationChecks = Field(
        default_factory=CompetingExplanationChecks
    )

    @classmethod
    def stub(cls) -> ConstructValidityClaims:
        """Return an obviously-placeholder stub for ``--init-claims``."""
        return cls(
            mastery_sense=MasterySenseClaim(
                sense="evaluative",
                description="FILL IN: the analyst's articulation of what mastery means here.",
            ),
            scope=ScopeClaim(
                scope="items_in_benchmark",
                justification="FILL IN: why this scope is appropriate.",
            ),
            constitution=ConstitutionClaim(
                position="evidence_of_mastery",
                justification="FILL IN: brief explanation of the position taken.",
            ),
            carving=CarvingClaim(
                acknowledges_carving_indexed=False,
                notes="FILL IN if acknowledges_carving_indexed=true.",
            ),
            competing_explanations=CompetingExplanationChecks(),
        )


# ---- Verdict computation ---------------------------------------------------


@dataclass(frozen=True)
class ReportVerdict:
    """Deterministic summary verdict computed from the claims + evidence."""

    label: Literal["defensible", "partially_defensible", "not_defensible"]
    one_liner: str
    rationale: list[str]


# ---- Negative-findings aggregation (Phase 3.2) ---------------------------


@dataclass(frozen=True)
class NegativeFinding:
    """One auto-collected negative finding from a Phase 2 artifact.

    A finding is "negative" in the construct-validity sense — a check
    that ran and returned a result that *weakens or complicates* the
    mastery claim. Per *Closing the Construct-Validity Gap in infereval*
    (Phase 3.2 / R21), the framework surfaces these by default in the
    report.
    """

    source: Literal["structure", "sweep", "model_fit"]
    summary: str
    """One-line description rendered in the Negative findings section."""


def collect_negative_findings(
    *,
    structure_report: dict[str, object] | None = None,
    sweep_summary: dict[str, object] | None = None,
    model_fit: dict[str, object] | None = None,
    factor_kinds: dict[str, str] | None = None,
) -> list[NegativeFinding]:
    """Scan the supplied Phase 2 artifacts and return their negative findings.

    Sources:

    - **structure_report**: each anomaly across all checks is one finding.
    - **sweep_summary**: instability (verdict not "stable across the sweep
      range") is one finding.
    - **model_fit**: factors whose Wald p > 0.05 are surfaced as
      no-significant-effect findings. When ``factor_kinds`` supplies a
      valence label for a factor, the finding's summary explicitly
      states whether the null is a *weakening* of the mastery claim
      (a substantive factor that didn't differentiate) or a *strengthening*
      one (an experimentally-controlled factor that properly didn't
      affect behavior — e.g. the paraphrase axis). Unlabelled factors
      get the historical neutral summary so the analyst can read the
      valence from context.

    Parameters
    ----------
    factor_kinds
        Optional mapping ``factor_name -> {"substantive",
        "experimentally_controlled"}`` from ``Benchmark.factor_kinds``.
        When omitted, all null-effect findings are summarised neutrally.
    """
    findings: list[NegativeFinding] = []

    if structure_report is not None:
        checks_raw = structure_report.get("checks", [])
        checks = checks_raw if isinstance(checks_raw, list) else []
        for check in checks:
            if not isinstance(check, dict):
                continue
            anomalies = check.get("anomalies", ()) if isinstance(check, dict) else ()
            if not anomalies:
                continue
            check_name = check.get("name", "?")
            for a in anomalies:
                if isinstance(a, dict):
                    item_id = a.get("item_id", "?")
                    expl = a.get("explanation", "")
                    findings.append(
                        NegativeFinding(
                            source="structure",
                            summary=f"{check_name} / {item_id}: {expl}",
                        )
                    )

    if sweep_summary is not None:
        verdict_raw = sweep_summary.get("stability_verdict", "")
        verdict_str = str(verdict_raw).lower()
        # The SweepResult.stability_verdict strings live in three flavours:
        # "stable" (positive), "moderately sensitive" (negative),
        # "substantively" (negative). "Stable" doesn't appear in the
        # negative ones, so its absence is the right signal.
        if verdict_str and "stable" not in verdict_str:
            param = sweep_summary.get("parameter", "?")
            findings.append(
                NegativeFinding(
                    source="sweep",
                    summary=f"Sweep over `{param}`: {sweep_summary.get('stability_verdict')}",
                )
            )

    if model_fit is not None:
        wald_raw = model_fit.get("factor_wald", {})
        wald = wald_raw if isinstance(wald_raw, dict) else {}
        kinds = factor_kinds or {}
        for factor, p in wald.items():
            if not isinstance(p, (int, float)):
                continue
            if p > 0.05:
                kind = kinds.get(str(factor))
                if kind == "substantive":
                    valence = (
                        " — **weakens the mastery claim**: this factor was "
                        "declared substantive, so the model failing to "
                        "differentiate across its levels is a negative finding"
                    )
                elif kind == "experimentally_controlled":
                    valence = (
                        " — **strengthens the mastery claim**: this factor "
                        "was declared experimentally-controlled, so the null "
                        "result is the wanted outcome (content-not-form "
                        "behavior)"
                    )
                else:
                    valence = ""
                findings.append(
                    NegativeFinding(
                        source="model_fit",
                        summary=(
                            f"`{factor}`: Wald p = {p:.3f} "
                            f"(no significant effect detected){valence}"
                        ),
                    )
                )

    return findings


# Per-scope, which competing-explanation checks are *required* for the
# claim to be defensible. Stricter scopes require more checks.
_REQUIRED_CHECKS_BY_SCOPE: dict[str, frozenset[str]] = {
    "items_in_benchmark": frozenset({
        # Even the narrowest scope needs the within-benchmark hygiene.
        "structural_check_run",
        "sensitivity_sweep_run",
    }),
    "domain_D_as_sampled": frozenset({
        "structural_check_run",
        "sensitivity_sweep_run",
        "paraphrase_sweep_run",
        "cross_panel_check_run",
        "held_out_items_used",
    }),
    "general_capacity": frozenset({
        "structural_check_run",
        "sensitivity_sweep_run",
        "paraphrase_sweep_run",
        "cross_panel_check_run",
        "held_out_items_used",
        "training_data_separation_verified",
        "cross_domain_comparison_run",
        "replication_attempted",
    }),
}


def compute_verdict(
    claims: ConstructValidityClaims,
    *,
    structure_report: dict[str, object] | None = None,
    benchmark: Benchmark | None = None,
) -> ReportVerdict:
    """Return the deterministic summary verdict for the claims + evidence.

    The verdict is computed against the *claims* file together with the
    supplied analytical artifacts. When no artifacts are passed
    (``structure_report=None``, ``benchmark=None``), the verdict is
    computed from claims alone and a "verdict computed unaudited"
    rationale line is added so the reader can tell.

    The deterministic rule:

    - "defensible" iff every check required by the declared scope is
      marked True AND no audited check returned a failing artifact AND
      the carving claim is explicit (acknowledges = True iff any
      in-principle claims are being made) AND the benchmark supports
      an inter-analyst baseline when one is required by the scope.
    - "not_defensible" iff *more than half* of the required checks
      are missing.
    - "partially_defensible" otherwise — including the "ran but didn't
      pass" cases (structural anomalies present, single-analyst benchmark
      with ``items_in_benchmark`` scope).

    Audit caps (added in v0.5.3 from external review):

    - If ``structure_report`` is supplied AND ``structural_check_run``
      is marked True AND the report contains any anomaly, the structural
      check is treated as failing — the verdict is capped at
      ``partially_defensible`` with a rationale line naming the count.
    - If ``benchmark`` is supplied AND the scope is
      ``items_in_benchmark`` AND ``len(benchmark.analysts) < 2``, the
      verdict is capped at ``partially_defensible`` with a rationale
      line surfacing the panel size — agreement with a single analyst
      cannot inherit the convergent-validity guarantee that
      multi-analyst agreement carries.

    Backwards-compatible callers that don't pass the artifacts get
    behaviour identical to v0.5.2 except for the additional "verdict
    computed unaudited" rationale line.
    """
    required = _REQUIRED_CHECKS_BY_SCOPE[claims.scope.scope]
    ce = claims.competing_explanations
    present = {name for name in required if getattr(ce, name)}
    missing = required - present

    rationale = []
    if not missing:
        rationale.append(
            f"All {len(required)} competing-explanation checks required for "
            f"scope={claims.scope.scope!r} are marked as run."
        )
    else:
        rationale.append(
            f"{len(missing)} of {len(required)} required checks NOT run: "
            f"{sorted(missing)}."
        )

    # Carving check applies only when scope reaches beyond items_in_benchmark.
    carving_ok = True
    if claims.scope.scope != "items_in_benchmark":
        if not claims.carving.acknowledges_carving_indexed:
            carving_ok = False
            rationale.append(
                f"Scope={claims.scope.scope!r} reaches beyond the items "
                "themselves, but carving-indexed framing is NOT acknowledged "
                "(R19 unaddressed)."
            )
        elif not claims.carving.notes.strip():
            carving_ok = False
            rationale.append(
                "Carving acknowledged but no notes supplied; R19 requires "
                "the carving to be documented."
            )

    # Audit caps (v0.5.3): downgrade when the analyst declared a check
    # was run but the corresponding artifact tells a different story.
    structural_failed = False
    if (
        structure_report is not None
        and getattr(ce, "structural_check_run", False)
    ):
        checks_obj = structure_report.get("checks") or []
        checks_iter = checks_obj if isinstance(checks_obj, list) else []
        total_anomalies = 0
        for check in checks_iter:
            if not isinstance(check, dict):
                continue
            anomalies = check.get("anomalies", ())
            if isinstance(anomalies, (list, tuple)):
                total_anomalies += len(anomalies)
        if total_anomalies > 0:
            structural_failed = True
            rationale.append(
                f"`structural_check_run` is marked True, but the supplied "
                f"structure report contains {total_anomalies} anomal"
                f"{'y' if total_anomalies == 1 else 'ies'} — "
                "the check ran but did not pass. Verdict capped at "
                "partially_defensible."
            )

    panel_too_small = False
    panel_size: int | None = None
    if benchmark is not None and claims.scope.scope == "items_in_benchmark":
        panel_size = len(benchmark.analysts)
        if panel_size < 2:
            panel_too_small = True
            rationale.append(
                f"Benchmark has m={panel_size} analyst(s); κ_F\\*(β) is "
                "undefined and there is no independent reference column. "
                "A green verdict at items_in_benchmark scope would certify "
                "agreement with a single labeler — capped at "
                "partially_defensible."
            )

    if structure_report is None and benchmark is None:
        rationale.append(
            "Verdict computed unaudited: no structure_report or benchmark "
            "supplied to compute_verdict, so 'check run' is taken at face "
            "value and panel size is not inspected. Render through "
            "`infereval report` (which passes both) for the audited verdict."
        )

    # Decide.
    audit_passes = not structural_failed and not panel_too_small
    if not missing and carving_ok and audit_passes:
        one_liner = f"Mastery claim defensible at scope={claims.scope.scope!r}."
        if panel_size is not None:
            one_liner = (
                f"Mastery claim defensible at scope={claims.scope.scope!r} "
                f"(m={panel_size} analysts)."
            )
        return ReportVerdict(
            label="defensible",
            one_liner=one_liner,
            rationale=rationale,
        )
    if (len(missing) > len(required) / 2 or not carving_ok) and audit_passes:
        return ReportVerdict(
            label="not_defensible",
            one_liner=(
                f"Mastery claim NOT defensible from the supplied evidence at "
                f"scope={claims.scope.scope!r}."
            ),
            rationale=rationale,
        )
    return ReportVerdict(
        label="partially_defensible",
        one_liner=(
            f"Mastery claim partially defensible at scope={claims.scope.scope!r} — "
            "see Unaddressed competing explanations."
        ),
        rationale=rationale,
    )


# ---- Rendering ------------------------------------------------------------


def render_markdown(
    *,
    evaluation: Evaluation,
    benchmark: Benchmark,
    claims: ConstructValidityClaims,
    structure_report: dict[str, object] | None = None,
    sweep_summary: dict[str, object] | None = None,
    model_fit: dict[str, object] | None = None,
    generated_at: datetime | None = None,
    suppress_negatives: bool = False,
) -> str:
    """Produce the construct-validity report as Markdown.

    Optional arguments (``structure_report``, ``sweep_summary``,
    ``model_fit``) populate the Evidence section; when absent, that
    section explicitly notes the missing evidence.
    """
    from .metrics import (
        cohens_kappa,
        consensus_reference,
        coverage,
        fleiss_kappa,
        inter_analyst_fleiss,
    )

    generated_at = generated_at or datetime.now(timezone.utc)

    kappa_c = cohens_kappa(evaluation, consensus_reference(evaluation))
    kappa_f = fleiss_kappa(evaluation)
    kappa_f_star = inter_analyst_fleiss(benchmark)
    cov = coverage(evaluation)
    verdict = compute_verdict(
        claims,
        structure_report=structure_report,
        benchmark=benchmark,
    )

    # Collect negative findings up-front so we can both render them and
    # apply the suppression penalty to the verdict in one place.
    findings = collect_negative_findings(
        structure_report=structure_report,
        sweep_summary=sweep_summary,
        model_fit=model_fit,
        factor_kinds=dict(benchmark.factor_kinds) if benchmark.factor_kinds else None,
    )
    any_phase2_supplied = any(
        x is not None for x in (structure_report, sweep_summary, model_fit)
    )

    # If suppression is enabled, the Summary verdict downgrades one tier:
    # defensible -> partially_defensible -> not_defensible. Hiding
    # evidence is itself a negative construct-validity signal.
    if suppress_negatives:
        downgraded_label = {
            "defensible": "partially_defensible",
            "partially_defensible": "not_defensible",
            "not_defensible": "not_defensible",
        }[verdict.label]
        if downgraded_label != verdict.label:
            verdict = ReportVerdict(
                label=downgraded_label,  # type: ignore[arg-type]
                one_liner=(
                    "Verdict downgraded one tier because "
                    "--suppress-negatives is enabled."
                ),
                rationale=[
                    *verdict.rationale,
                    "Negative-findings suppression downgrades the verdict "
                    "(Phase 3.2 / R21).",
                ],
            )

    lines: list[str] = []
    lines.append("# Construct-validity report")
    lines.append("")
    lines.append(f"_Generated: {generated_at.isoformat()}_")
    if suppress_negatives:
        lines.append("")
        lines.append(
            "> ⚠️ **Negative-findings suppression: ENABLED.** This is an "
            "explicit author choice via `--suppress-negatives`; the "
            "framework normally surfaces negative findings by default. "
            "Reviewers: ask why this flag was set."
        )
    lines.append("")

    # 1. Identity
    lines.append("## 1. Identity")
    lines.append("")
    lines.append(f"- **Evaluation**: `{evaluation.id}`")
    lines.append(f"- **Benchmark**: `{benchmark.id}`")
    lines.append(
        f"- **Model**: `{evaluation.model.provider}` / `{evaluation.model.model_id}`"
    )
    if evaluation.started_at:
        lines.append(f"- **Run started**: {evaluation.started_at.isoformat()}")
    lines.append(f"- **Items**: {evaluation.n}")
    lines.append(f"- **Analysts**: {benchmark.m}")
    lines.append("")

    # 2. Summary metrics
    lines.append("## 2. Summary metrics")
    lines.append("")
    lines.append(f"- **Coverage**: {cov:.4f}")
    lines.append(f"- **Cohen's κ_C (vs consensus)**: {_format_kappa(kappa_c)}")
    lines.append(f"- **Fleiss' κ_F**: {_format_kappa(kappa_f)}")
    lines.append(f"- **Inter-analyst κ_F\\***: {_format_kappa(kappa_f_star)}")
    lines.append("")

    # 3. Construct-validity claims (R16-R20)
    lines.append("## 3. Construct-validity claims (R16–R20)")
    lines.append("")
    lines.append(f"**Mastery sense (R16)**: {claims.mastery_sense.sense}")
    lines.append("")
    lines.append(f"> {claims.mastery_sense.description}")
    lines.append("")
    lines.append(f"**Scope (R17)**: {claims.scope.scope}")
    lines.append("")
    lines.append(f"> {claims.scope.justification}")
    lines.append("")
    lines.append(f"**Constitution vs. evidence (R18)**: {claims.constitution.position}")
    lines.append("")
    lines.append(f"> {claims.constitution.justification}")
    lines.append("")
    carving_status = (
        "acknowledged" if claims.carving.acknowledges_carving_indexed else "not acknowledged"
    )
    lines.append(f"**Carving-indexed framing (R19)**: {carving_status}")
    if claims.carving.notes.strip():
        lines.append("")
        lines.append(f"> {claims.carving.notes}")
    lines.append("")

    # 4. Evidence
    lines.append("## 4. Evidence")
    lines.append("")
    lines.append("Auto-collected from optional Phase 2 artifacts:")
    lines.append("")

    if structure_report is not None:
        total_anomalies = structure_report.get("total_anomalies", 0)
        lines.append(
            f"- **Structural coherence checks** (R13): "
            f"{total_anomalies} anomalies flagged across the bundled checks."
        )
    else:
        lines.append("- **Structural coherence checks** (R13): NOT SUPPLIED.")

    if sweep_summary is not None:
        kc_range = sweep_summary.get("kappa_c_range")
        param = sweep_summary.get("parameter", "?")
        verdict_str = sweep_summary.get("stability_verdict", "?")
        if kc_range is not None:
            lines.append(
                f"- **Sensitivity sweep** over `{param}` (R11): "
                f"κ_C range = {kc_range:.3f}. {verdict_str}"
            )
        else:
            lines.append(
                f"- **Sensitivity sweep** over `{param}` (R11): {verdict_str}"
            )
    else:
        lines.append("- **Sensitivity sweep** (R11): NOT SUPPLIED.")

    if model_fit is not None:
        wald_raw = model_fit.get("factor_wald", {})
        wald = wald_raw if isinstance(wald_raw, dict) else {}
        sig = sum(1 for p in wald.values() if isinstance(p, (int, float)) and p < 0.05)
        lines.append(
            f"- **Factor-effects model fit** (R7, R12): "
            f"{sig}/{len(wald)} factors significant at α=0.05."
        )
    else:
        lines.append("- **Factor-effects model fit** (R7, R12): NOT SUPPLIED.")
    lines.append("")

    # 4b. Negative findings (Phase 3.2, R21)
    lines.append("## 4b. Negative findings")
    lines.append("")
    if suppress_negatives:
        lines.append(
            "⚠️ **Suppressed via `--suppress-negatives`.** This is an "
            "explicit author choice; the framework normally surfaces "
            "negative findings by default. Reviewers: ask why this flag "
            "was set."
        )
    elif not any_phase2_supplied:
        lines.append(
            "No Phase 2 artifacts supplied; the auto-collection step had "
            "nothing to scan. See Unaddressed competing explanations (§5) "
            "for the analyst-declared check status."
        )
    elif not findings:
        lines.append("No negative findings detected in the supplied Phase 2 artifacts.")
    else:
        lines.append(
            "The framework auto-collects negative findings from the "
            "supplied Phase 2 artifacts. Each item below represents a "
            "check that ran but returned a finding that *weakens or "
            "complicates* the mastery claim."
        )
        lines.append("")
        # Group by source for readability.
        for src_label, src_key in [
            ("Structural anomalies", "structure"),
            ("Sweep instability", "sweep"),
            ("Factor-effects null findings", "model_fit"),
        ]:
            src_items = [f for f in findings if f.source == src_key]
            if not src_items:
                continue
            lines.append(f"### {src_label} ({len(src_items)} flagged)")
            for f in src_items:
                lines.append(f"- {f.summary}")
            lines.append("")
    lines.append("")

    # 5. Unaddressed competing explanations
    lines.append("## 5. Unaddressed competing explanations")
    lines.append("")
    ce = claims.competing_explanations
    unaddressed = [
        (name, _human_label_for_check(name))
        for name in (
            "paraphrase_sweep_run",
            "sensitivity_sweep_run",
            "structural_check_run",
            "cross_panel_check_run",
            "independent_reference_panel_used",
            "held_out_items_used",
            "training_data_separation_verified",
            "cross_domain_comparison_run",
            "replication_attempted",
        )
        if not getattr(ce, name)
    ]
    if not unaddressed:
        lines.append("All declared competing-explanation checks marked as run.")
    else:
        lines.append(
            "The following checks were NOT run. Each omission weakens the "
            "defensibility of the corresponding mastery claim:"
        )
        lines.append("")
        for name, label in unaddressed:
            lines.append(f"- **{label}** (`{name}`)")
    lines.append("")

    # 6. Summary verdict
    lines.append("## 6. Summary verdict")
    lines.append("")
    badge = {
        "defensible": "✅",
        "partially_defensible": "⚠️",
        "not_defensible": "❌",
    }[verdict.label]
    lines.append(f"### {badge} {verdict.one_liner}")
    lines.append("")
    for note in verdict.rationale:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "*Generated by `infereval report` (Phase 3.1, R16–R20). The verdict "
        "is computed deterministically from the claims file; the framework "
        "refuses to render a 'defensible' verdict without the corresponding "
        "competing-explanation checks.*"
    )

    return "\n".join(lines) + "\n"


def _format_kappa(value: float | None) -> str:
    if value is None:
        return "undefined"
    return f"{value:+.4f}"


def _human_label_for_check(name: str) -> str:
    return name.replace("_", " ").capitalize()


__all__ = [
    "CarvingClaim",
    "CompetingExplanationChecks",
    "ConstitutionClaim",
    "ConstructValidityClaims",
    "MasterySenseClaim",
    "NegativeFinding",
    "ReportVerdict",
    "ScopeClaim",
    "collect_negative_findings",
    "compute_verdict",
    "render_markdown",
]

# Used by the CLI for --init-claims; kept here so the JSON shape stays
# next to the schema.
_ = json
