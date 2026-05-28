"""Stage-4 tests for R22 (test-retest reliability) integration in the
construct-validity report.

Covers:
- ``CompetingExplanationChecks.test_retest_run`` field exists and
  defaults to False.
- ``_REQUIRED_CHECKS_BY_SCOPE`` includes ``test_retest_run`` at
  ``domain_D_as_sampled`` and ``general_capacity``, but NOT at
  ``items_in_benchmark``.
- ``compute_verdict`` audit-cap: if ``test_retest_run`` is asserted
  but the supplied RetestResult is substantively-unstable or has
  undefined κ, the verdict caps at ``partially_defensible``.
- ``collect_negative_findings`` emits a corpus-level finding for
  non-stable verdicts and per-item findings for flipped items (capped).
- ``render_markdown`` includes the test-retest κ row in section 2 and
  a test-retest negatives subsection in 4b when an artifact is supplied.
- The stub claims file (``ConstructValidityClaims.stub()``) includes
  the new field default-False.
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
    collect_negative_findings,
    compute_verdict,
    render_markdown,
)

STOP_SIGN_PATH = Path(__file__).parent.parent.parent / "examples" / "stop_sign" / "benchmark.json"


# ---- Field + scope-requirement plumbing ----------------------------------


def test_competing_explanation_checks_has_test_retest_run_field() -> None:
    ce = CompetingExplanationChecks()
    assert hasattr(ce, "test_retest_run")
    assert ce.test_retest_run is False


def test_stub_claims_include_test_retest_run_field() -> None:
    stub = ConstructValidityClaims.stub()
    assert stub.competing_explanations.test_retest_run is False


def test_test_retest_run_required_at_domain_D_as_sampled() -> None:  # noqa: N802 -- mirrors scope literal
    """At domain_D_as_sampled scope, omitting test_retest_run prevents
    the verdict from being defensible."""
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
            test_retest_run=False,
        ),
    )
    v = compute_verdict(claims)
    assert v.label != "defensible"
    assert any("test_retest_run" in r for r in v.rationale)


def test_test_retest_run_NOT_required_at_items_in_benchmark() -> None:  # noqa: N802 -- mirrors scope literal
    """At items_in_benchmark scope, test_retest_run is optional."""
    claims = ConstructValidityClaims(
        mastery_sense={"sense": "evaluative", "description": "x"},
        scope={"scope": "items_in_benchmark", "justification": "x"},
        constitution={"position": "evidence_of_mastery", "justification": "x"},
        carving={"acknowledges_carving_indexed": False, "notes": ""},
        competing_explanations=CompetingExplanationChecks(
            structural_check_run=True,
            sensitivity_sweep_run=True,
            # test_retest_run omitted on purpose
        ),
    )
    # No artifacts supplied -> verdict should still be defensible at this scope
    v = compute_verdict(claims)
    assert v.label == "defensible"


def test_test_retest_run_required_at_general_capacity() -> None:
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
            test_retest_run=False,  # the one omission
        ),
    )
    v = compute_verdict(claims)
    assert v.label != "defensible"


# ---- Audit cap: substantively unstable retest ----------------------------


def _full_domain_d_claims() -> ConstructValidityClaims:
    return ConstructValidityClaims(
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
        # v0.6.1 R22 second leg: declared identity criterion required at
        # scope >= domain_D_as_sampled when test_retest_run=True.
        # Tests that want to exercise the *substantively-unstable* and
        # *stable* paths use this default-fully-populated claims object;
        # tests that want to exercise the *undeclared-criterion* path
        # construct the claims object without the reliability block.
        reliability={
            "identity_criterion": {
                "same_provider_model_id": True,
                "cross_update_identity_asserted": True,
                "same_scaffolding": True,
                "unverifiable_caveats": "x",
                "rationale": "x",
            }
        },
    )


def test_substantively_unstable_retest_caps_verdict() -> None:
    """All-checks-marked + carving acknowledged, but the supplied
    retest is substantively unstable -> partially_defensible (not
    defensible)."""
    retest_result = {
        "stability_verdict": (
            "test-retest reliability is substantively unstable (κ = +0.300); "
            "30.0% of items flipped between runs."
        ),
        "test_retest_kappa": 0.3,
        "flip_rate": 0.3,
        "flipped_items": [],
    }
    v = compute_verdict(_full_domain_d_claims(), retest_result=retest_result)
    assert v.label == "partially_defensible"
    assert any("substantively unstable" in r for r in v.rationale)


def test_stable_retest_does_not_cap() -> None:
    retest_result = {
        "stability_verdict": (
            "test-retest reliability is stable (κ = +0.900); verdict-flip "
            "rate 5.0%."
        ),
        "test_retest_kappa": 0.9,
        "flip_rate": 0.05,
        "flipped_items": [],
    }
    v = compute_verdict(_full_domain_d_claims(), retest_result=retest_result)
    assert v.label == "defensible"


def test_undefined_retest_kappa_caps_verdict() -> None:
    retest_result = {
        "stability_verdict": (
            "test-retest κ is undefined on this comparison (degenerate "
            "agreement structure); reliability cannot be assessed from "
            "this run pair"
        ),
        "test_retest_kappa": None,
        "flip_rate": 0.0,
        "flipped_items": [],
    }
    v = compute_verdict(_full_domain_d_claims(), retest_result=retest_result)
    assert v.label == "partially_defensible"
    assert any("undefined" in r for r in v.rationale)


def test_retest_audit_cap_does_not_fire_when_check_not_asserted() -> None:
    """If test_retest_run is False, supplying a retest artifact doesn't
    cap the verdict — the audit cap only fires on claimed checks."""
    claims = ConstructValidityClaims(
        mastery_sense={"sense": "evaluative", "description": "x"},
        scope={"scope": "items_in_benchmark", "justification": "x"},
        constitution={"position": "evidence_of_mastery", "justification": "x"},
        carving={"acknowledges_carving_indexed": False, "notes": ""},
        competing_explanations=CompetingExplanationChecks(
            structural_check_run=True,
            sensitivity_sweep_run=True,
            test_retest_run=False,  # not asserted
        ),
    )
    retest_result = {
        "stability_verdict": "test-retest reliability is substantively unstable",
        "test_retest_kappa": 0.2,
        "flip_rate": 0.4,
        "flipped_items": [],
    }
    v = compute_verdict(claims, retest_result=retest_result)
    # items_in_benchmark scope; test_retest_run not asserted -> no cap
    # (no test_retest_run required there either).
    assert v.label == "defensible"


# ---- Negative findings ---------------------------------------------------


def test_unstable_retest_produces_corpus_level_negative_finding() -> None:
    retest_result = {
        "stability_verdict": (
            "test-retest reliability is substantively unstable (κ = +0.200); "
            "40.0% of items flipped between runs — model output for this "
            "benchmark is not reliable enough for the headline κ_C to be "
            "interpreted as signal."
        ),
        "test_retest_kappa": 0.2,
        "flip_rate": 0.4,
        "flipped_items": [],
    }
    findings = collect_negative_findings(retest_result=retest_result)
    assert any(f.source == "retest" for f in findings)
    retest_finding = next(f for f in findings if f.source == "retest")
    assert "R22" in retest_finding.summary or "Test-retest" in retest_finding.summary


def test_flipped_items_emit_per_item_negative_findings() -> None:
    retest_result = {
        "stability_verdict": (
            "test-retest reliability is moderately stable (κ = +0.700); "
            "20.0% of items flipped between runs."
        ),
        "test_retest_kappa": 0.7,
        "flip_rate": 0.2,
        "flipped_items": [
            {"item_id": "a1", "verdict_a": "good", "verdict_b": "bad",
             "factor_levels": {"side_premise_type": "defeater"}},
            {"item_id": "a2", "verdict_a": "good", "verdict_b": "bad",
             "factor_levels": None},
        ],
    }
    findings = collect_negative_findings(retest_result=retest_result)
    retest_findings = [f for f in findings if f.source == "retest"]
    # 1 corpus-level + 2 per-item
    assert len(retest_findings) == 3
    assert any("a1" in f.summary for f in retest_findings)
    assert any("a2" in f.summary for f in retest_findings)


def test_stable_retest_produces_no_negative_findings() -> None:
    retest_result = {
        "stability_verdict": (
            "test-retest reliability is stable (κ = +0.950); "
            "2.0% of items flipped between runs."
        ),
        "test_retest_kappa": 0.95,
        "flip_rate": 0.02,
        "flipped_items": [],
    }
    findings = collect_negative_findings(retest_result=retest_result)
    retest_findings = [f for f in findings if f.source == "retest"]
    assert retest_findings == []


def test_flipped_items_cap_at_50() -> None:
    retest_result = {
        "stability_verdict": (
            "test-retest reliability is substantively unstable (κ = +0.100)"
        ),
        "test_retest_kappa": 0.1,
        "flip_rate": 0.6,
        "flipped_items": [
            {"item_id": f"i{i}", "verdict_a": "good", "verdict_b": "bad",
             "factor_levels": None}
            for i in range(60)
        ],
    }
    findings = collect_negative_findings(retest_result=retest_result)
    retest_findings = [f for f in findings if f.source == "retest"]
    # 1 corpus-level + 50 per-item + 1 "... and 10 more" overflow
    assert len(retest_findings) == 52
    assert any("10 more flipped" in f.summary for f in retest_findings)


# ---- Rendering ------------------------------------------------------------


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


def test_render_markdown_includes_test_retest_row_when_retest_supplied() -> None:
    bench, eta = _bench_eta_with_extra_analyst()
    claims = ConstructValidityClaims.stub()
    retest_result = {
        "stability_verdict": "test-retest reliability is stable (κ = +0.850); flip 5.0%.",
        "test_retest_kappa": 0.85,
        "flip_rate": 0.05,
        "flipped_items": [],
    }
    md = render_markdown(
        evaluation=eta,
        benchmark=bench,
        claims=claims,
        retest_result=retest_result,
    )
    # Section 2 row
    assert "Test-retest κ (R22)" in md
    assert "+0.8500" in md
    # Section 4 evidence row
    assert "Test-retest reliability" in md and "R22" in md


def test_render_markdown_test_retest_not_supplied_shown_as_NOT_SUPPLIED() -> None:  # noqa: N802 -- mirrors UI literal
    bench, eta = _bench_eta_with_extra_analyst()
    claims = ConstructValidityClaims.stub()
    md = render_markdown(
        evaluation=eta,
        benchmark=bench,
        claims=claims,
        # retest_result intentionally omitted
    )
    assert "Test-retest reliability" in md and "NOT SUPPLIED" in md


def test_render_markdown_includes_retest_negative_findings_subsection() -> None:
    bench, eta = _bench_eta_with_extra_analyst()
    claims = ConstructValidityClaims.stub()
    retest_result = {
        "stability_verdict": "test-retest reliability is substantively unstable (κ = +0.200); 40.0% of items flipped.",
        "test_retest_kappa": 0.2,
        "flip_rate": 0.4,
        "flipped_items": [
            {"item_id": "row-0", "verdict_a": "good", "verdict_b": "bad",
             "factor_levels": None},
        ],
    }
    md = render_markdown(
        evaluation=eta,
        benchmark=bench,
        claims=claims,
        retest_result=retest_result,
    )
    assert "Test-retest anomalies (R22)" in md
    assert "row-0" in md
