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
    carving-indexed form Remark 9 specifies."""
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


def compute_verdict(claims: ConstructValidityClaims) -> ReportVerdict:
    """Return the deterministic summary verdict for the claims as declared.

    The verdict is computed only against the *claims* file — the
    framework trusts the analyst's declared booleans (the audit of
    whether those declarations are accurate is the report reader's
    job). The deterministic rule:

    - "defensible" iff every check required by the declared scope is
      marked True AND the carving claim is explicit (acknowledges =
      True iff any in-principle claims are being made).
    - "not_defensible" iff *more than half* of the required checks
      are missing.
    - "partially_defensible" otherwise.
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

    # Decide.
    if not missing and carving_ok:
        return ReportVerdict(
            label="defensible",
            one_liner=f"Mastery claim defensible at scope={claims.scope.scope!r}.",
            rationale=rationale,
        )
    if len(missing) > len(required) / 2 or not carving_ok:
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
    verdict = compute_verdict(claims)

    lines: list[str] = []
    lines.append("# Construct-validity report")
    lines.append("")
    lines.append(f"_Generated: {generated_at.isoformat()}_")
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
    "ReportVerdict",
    "ScopeClaim",
    "compute_verdict",
    "render_markdown",
]

# Used by the CLI for --init-claims; kept here so the JSON shape stays
# next to the schema.
_ = json
