"""Stage-3 tests for the v0.6.1 R22 second-leg gate (individuation
criterion declared) + renderer surfacing of the criterion.

Covers:
- R22 satisfaction requires `test_retest_run=True` AND a declared
  `IdentityCriterion` at scope >= `domain_D_as_sampled`. Mirrors the
  R19 carving-acknowledgement gate exactly.
- At scope `items_in_benchmark`, the criterion is informational; no
  cap fires when it's missing.
- The criterion-undeclared cap stacks transparently with the
  v0.6.0 substantively-unstable cap (both fire when both conditions
  obtain).
- Renderer section 2 carries the criterion summary on the test-retest
  κ line.
- Renderer section 3 carries the full criterion block.
"""

from __future__ import annotations

import json
from pathlib import Path

from infereval.benchmark import Benchmark
from infereval.endorsement import EndorsementConfig
from infereval.evaluation import evaluate
from infereval.providers.mock import ScriptedProvider
from infereval.report import (
    CompetingExplanationChecks,
    ConstructValidityClaims,
    compute_verdict,
    render_markdown,
)

STOP_SIGN_PATH = Path(__file__).parent.parent.parent / "examples" / "stop_sign" / "benchmark.json"


def _declared_criterion_dict() -> dict:
    return {
        "same_provider_model_id": True,
        "cross_update_identity_asserted": True,
        "same_scaffolding": True,
        "unverifiable_caveats": "OpenAI snapshot fingerprint stable.",
        "rationale": "Two runs minutes apart on the same provider snapshot.",
    }


def _claims_with_criterion(scope: str = "domain_D_as_sampled") -> ConstructValidityClaims:
    return ConstructValidityClaims(
        mastery_sense={"sense": "standing", "description": "x"},
        scope={"scope": scope, "justification": "x"},
        constitution={"position": "evidence_of_mastery", "justification": "x"},
        carving={"acknowledges_carving_indexed": True, "notes": "x"},
        competing_explanations=CompetingExplanationChecks(
            structural_check_run=True,
            sensitivity_sweep_run=True,
            paraphrase_sweep_run=True,
            cross_panel_check_run=True,
            held_out_items_used=True,
            test_retest_run=True,
            # general_capacity needs the extras too; tests for that scope
            # use _claims_with_criterion("general_capacity") and supply
            # them via competing_explanations.model_copy(update=...).
        ),
        reliability={"identity_criterion": _declared_criterion_dict()},
    )


def _claims_without_criterion(scope: str = "domain_D_as_sampled") -> ConstructValidityClaims:
    return ConstructValidityClaims(
        mastery_sense={"sense": "standing", "description": "x"},
        scope={"scope": scope, "justification": "x"},
        constitution={"position": "evidence_of_mastery", "justification": "x"},
        carving={"acknowledges_carving_indexed": True, "notes": "x"},
        competing_explanations=CompetingExplanationChecks(
            structural_check_run=True,
            sensitivity_sweep_run=True,
            paraphrase_sweep_run=True,
            cross_panel_check_run=True,
            held_out_items_used=True,
            test_retest_run=True,
        ),
        # No reliability block — the new gate should cap the verdict.
    )


# ---- Gate behaviour ------------------------------------------------------


def test_undeclared_criterion_at_domain_d_caps_verdict() -> None:
    """At scope >= domain_D_as_sampled, R22 satisfaction requires a
    declared identity criterion. Without one, the verdict caps at
    partially_defensible — mirrors the R19 carving-acknowledgement
    gate."""
    v = compute_verdict(_claims_without_criterion("domain_D_as_sampled"))
    assert v.label == "partially_defensible"
    assert any(
        "identity criterion" in r and "not been declared" in r
        for r in v.rationale
    )


def test_declared_criterion_at_domain_d_clears_the_gate() -> None:
    v = compute_verdict(_claims_with_criterion("domain_D_as_sampled"))
    assert v.label == "defensible"


def test_undeclared_criterion_at_items_in_benchmark_does_not_cap() -> None:
    """At the narrowest scope, criterion is informational; no cap fires."""
    claims = ConstructValidityClaims(
        mastery_sense={"sense": "evaluative", "description": "x"},
        scope={"scope": "items_in_benchmark", "justification": "x"},
        constitution={"position": "evidence_of_mastery", "justification": "x"},
        carving={"acknowledges_carving_indexed": False, "notes": ""},
        competing_explanations=CompetingExplanationChecks(
            structural_check_run=True,
            sensitivity_sweep_run=True,
            test_retest_run=True,  # asserted but criterion undeclared
        ),
        # No reliability block.
    )
    v = compute_verdict(claims)
    assert v.label == "defensible"


def test_undeclared_criterion_at_general_capacity_caps_verdict() -> None:
    claims = ConstructValidityClaims(
        mastery_sense={"sense": "standing", "description": "x"},
        scope={"scope": "general_capacity", "justification": "x"},
        constitution={"position": "evidence_of_mastery", "justification": "x"},
        carving={"acknowledges_carving_indexed": True, "notes": "x"},
        competing_explanations=CompetingExplanationChecks(
            structural_check_run=True,
            sensitivity_sweep_run=True,
            paraphrase_sweep_run=True,
            cross_panel_check_run=True,
            held_out_items_used=True,
            training_data_separation_verified=True,
            cross_domain_comparison_run=True,
            replication_attempted=True,
            test_retest_run=True,
        ),
        # No reliability block.
    )
    v = compute_verdict(claims)
    assert v.label != "defensible"
    assert any(
        "identity criterion" in r and "not been declared" in r
        for r in v.rationale
    )


def test_empty_rationale_caps_verdict() -> None:
    """A reliability block with an empty `rationale` is not a real
    declaration — the gate treats it the same as missing."""
    claims = ConstructValidityClaims(
        mastery_sense={"sense": "standing", "description": "x"},
        scope={"scope": "domain_D_as_sampled", "justification": "x"},
        constitution={"position": "evidence_of_mastery", "justification": "x"},
        carving={"acknowledges_carving_indexed": True, "notes": "x"},
        competing_explanations=CompetingExplanationChecks(
            structural_check_run=True,
            sensitivity_sweep_run=True,
            paraphrase_sweep_run=True,
            cross_panel_check_run=True,
            held_out_items_used=True,
            test_retest_run=True,
        ),
        reliability={
            "identity_criterion": {
                "same_provider_model_id": True,
                "cross_update_identity_asserted": True,
                "same_scaffolding": True,
                "unverifiable_caveats": "x",
                "rationale": "   ",  # whitespace-only -> treated as empty
            }
        },
    )
    v = compute_verdict(claims)
    assert v.label == "partially_defensible"


def test_undeclared_criterion_cap_stacks_with_substantively_unstable_cap() -> None:
    """Both caps fire when both conditions obtain. Verdict still caps."""
    retest_result = {
        "stability_verdict": (
            "test-retest reliability is substantively unstable (κ = +0.300)"
        ),
        "test_retest_kappa": 0.3,
        "flip_rate": 0.3,
        "flipped_items": [],
    }
    v = compute_verdict(
        _claims_without_criterion("domain_D_as_sampled"),
        retest_result=retest_result,
    )
    assert v.label == "partially_defensible"
    # Both rationale lines should be present.
    assert any("substantively unstable" in r for r in v.rationale)
    assert any("not been declared" in r for r in v.rationale)


# ---- Renderer ------------------------------------------------------------


def _bench_eta_with_extra_analyst() -> tuple[Benchmark, object]:
    """2-analyst stop-sign so the m<2 cap doesn't compound."""
    data = json.loads(STOP_SIGN_PATH.read_text())
    data["analysts"].append({"id": "second", "display_name": "second analyst"})
    for it in data["items"]:
        it["analyst_verdicts"].append(it["analyst_verdicts"][0])
    bench = Benchmark.model_validate(data)
    provider = ScriptedProvider(responses=["GOOD"] * 12)
    eta = evaluate(bench, provider, config=EndorsementConfig(n_samples=1))
    return bench, eta


def test_section_2_carries_criterion_summary() -> None:
    bench, eta = _bench_eta_with_extra_analyst()
    claims = ConstructValidityClaims.stub()
    retest_result = {
        "stability_verdict": (
            "test-retest reliability is stable (κ = +0.85) "
            "under the declared identity criterion."
        ),
        "test_retest_kappa": 0.85,
        "flip_rate": 0.05,
        "flipped_items": [],
        "identity_criterion": _declared_criterion_dict(),
    }
    md = render_markdown(
        evaluation=eta,
        benchmark=bench,
        claims=claims,
        retest_result=retest_result,
    )
    assert "Test-retest κ (R22)" in md
    assert "+0.8500" in md
    assert "under the declared identity criterion" in md
    assert "provider+model_id" in md
    assert "cross-update identity asserted" in md
    assert "scaffolding constant" in md


def test_section_2_omits_criterion_clause_when_criterion_absent() -> None:
    bench, eta = _bench_eta_with_extra_analyst()
    claims = ConstructValidityClaims.stub()
    retest_result = {
        "stability_verdict": "test-retest reliability is stable (κ = +0.85)",
        "test_retest_kappa": 0.85,
        "flip_rate": 0.05,
        "flipped_items": [],
        # No identity_criterion key — pre-v0.6.1 retest artifact shape.
    }
    md = render_markdown(
        evaluation=eta,
        benchmark=bench,
        claims=claims,
        retest_result=retest_result,
    )
    assert "Test-retest κ (R22)" in md
    # The criterion clause should not appear when the artifact doesn't
    # carry it.
    assert "under the declared identity criterion" not in md.split(
        "## 3. Construct-validity claims"
    )[0]


def test_section_3_renders_full_criterion_block_when_claims_include_reliability() -> None:
    bench, eta = _bench_eta_with_extra_analyst()
    claims = _claims_with_criterion("domain_D_as_sampled")
    md = render_markdown(
        evaluation=eta,
        benchmark=bench,
        claims=claims,
    )
    assert "Reliability — identity criterion (R22, doubly-relative)" in md
    assert "Framework-substantiated" in md
    assert "Analyst-substantiated" in md
    assert "Unverifiable caveats" in md
    assert "Rationale" in md


def test_section_3_omits_reliability_block_when_claims_have_none() -> None:
    bench, eta = _bench_eta_with_extra_analyst()
    claims = _claims_without_criterion("domain_D_as_sampled")
    # claims.reliability is None here.
    md = render_markdown(
        evaluation=eta,
        benchmark=bench,
        claims=claims,
    )
    assert "Reliability — identity criterion" not in md
