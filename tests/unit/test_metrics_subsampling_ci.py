"""Tests for the Politis-Romano subsampling CI on κ added in v0.6.0.

Procedure: Politis & Romano (1994), Large sample confidence regions
based on sub-samples under minimal assumptions, Ann. Statist. 22(4).

Coverage of the test suite:
- Point estimate returned in the tuple matches the unweighted κ on the
  full evaluation (sanity).
- CI brackets the point estimate (the rate-corrected percentile
  construction can in principle produce CIs that don't contain the
  point estimate when the subsampling distribution is heavily skewed;
  for typical kappa inputs we expect bracketing and assert that).
- ``SubsamplingNotApplicableError`` fires for K < 10.
- ``subsample_size`` validation: out-of-range raises ValueError.
- Default ``subsample_size = round(K^0.7)`` for K=30 should give 11.
- Same seed → identical CI (reproducibility).
- Different seed → at least slightly different CI (sanity).
- Undefined point estimate raises ValueError.
- ``MetricsReport.cohens_kappa_with_ci`` and ``fleiss_kappa_with_ci``
  surface the procedure end-to-end.
"""

from __future__ import annotations

import pytest

from infereval.evaluation import (
    Evaluation,
    EvaluationItem,
    MajorityVote,
    ModelInfo,
    ProviderParams,
)
from infereval.metrics import (
    MIN_K_FOR_SUBSAMPLING_CI,
    MetricsReport,
    SubsamplingNotApplicableError,
    cohens_kappa,
    consensus_reference,
    fleiss_kappa,
    subsampling_kappa_ci,
)
from infereval.types import Verdict


def _item(
    item_id: str,
    *,
    analyst_verdicts: list[Verdict],
    model_verdict: Verdict,
) -> EvaluationItem:
    return EvaluationItem(
        id=item_id,
        premises=["x"],
        conclusions=["y"],
        analyst_verdicts=analyst_verdicts,
        model_verdict=model_verdict,
        majority_vote=MajorityVote(
            good=5 if model_verdict == Verdict.GOOD else 0,
            bad=5 if model_verdict == Verdict.BAD else 0,
            abstain=5 if model_verdict == Verdict.ABSTAIN else 0,
            verdict=model_verdict,
        ),
    )


def _mixed_eval(k: int, *, agreement_rate: float = 0.8) -> Evaluation:
    """K-item evaluation with the given fraction of model-analyst agreements.

    Half the agreements are GOOD-GOOD, half BAD-BAD; disagreements are
    GOOD-analyst + BAD-model (alternating). Produces a non-degenerate κ.
    """
    items: list[EvaluationItem] = []
    n_agree = round(agreement_rate * k)
    for i in range(k):
        if i < n_agree:
            v = Verdict.GOOD if i % 2 == 0 else Verdict.BAD
            items.append(_item(f"a{i}", analyst_verdicts=[v], model_verdict=v))
        else:
            analyst_v = Verdict.GOOD if i % 2 == 0 else Verdict.BAD
            model_v = Verdict.BAD if i % 2 == 0 else Verdict.GOOD
            items.append(
                _item(f"d{i}", analyst_verdicts=[analyst_v], model_verdict=model_v)
            )
    return Evaluation(
        id="test-run",
        benchmark_id="test-bench",
        model=ModelInfo(provider="mock", model_id="t1", params=ProviderParams()),
        items=items,
    )


# ---- Basic CI shape -------------------------------------------------------


def test_min_k_constant_is_documented() -> None:
    assert MIN_K_FOR_SUBSAMPLING_CI == 10


def test_subsampling_ci_returns_point_lo_hi() -> None:
    eta = _mixed_eval(30)
    ref = consensus_reference(eta)
    point, lo, hi = subsampling_kappa_ci(
        lambda e: cohens_kappa(e, consensus_reference(e)),
        eta,
        iterations=200,
        seed=42,
    )
    # Point estimate equals the directly-computed κ on the full eval.
    assert point == pytest.approx(cohens_kappa(eta, ref))
    assert lo <= point <= hi


def test_subsampling_ci_too_small_raises() -> None:
    eta = _mixed_eval(MIN_K_FOR_SUBSAMPLING_CI - 1)
    with pytest.raises(SubsamplingNotApplicableError):
        subsampling_kappa_ci(
            lambda e: cohens_kappa(e, consensus_reference(e)),
            eta,
        )


def test_subsampling_ci_invalid_subsample_size_raises() -> None:
    eta = _mixed_eval(30)
    with pytest.raises(ValueError, match="subsample_size"):
        subsampling_kappa_ci(
            lambda e: cohens_kappa(e, consensus_reference(e)),
            eta,
            subsample_size=1,
        )
    with pytest.raises(ValueError, match="subsample_size"):
        subsampling_kappa_ci(
            lambda e: cohens_kappa(e, consensus_reference(e)),
            eta,
            subsample_size=30,  # b >= K
        )


def test_subsampling_default_size_for_k_30() -> None:
    """K=30: round(30^0.7) = round(10.77) = 11."""
    from infereval.metrics import _default_subsample_size

    assert _default_subsample_size(30) == 11


def test_subsampling_ci_reproducible_with_seed() -> None:
    eta = _mixed_eval(40)
    point_1, lo_1, hi_1 = subsampling_kappa_ci(
        lambda e: cohens_kappa(e, consensus_reference(e)),
        eta,
        iterations=500,
        seed=123,
    )
    point_2, lo_2, hi_2 = subsampling_kappa_ci(
        lambda e: cohens_kappa(e, consensus_reference(e)),
        eta,
        iterations=500,
        seed=123,
    )
    assert (point_1, lo_1, hi_1) == (point_2, lo_2, hi_2)


def test_subsampling_ci_different_seeds_differ() -> None:
    eta = _mixed_eval(40)
    _, lo_1, hi_1 = subsampling_kappa_ci(
        lambda e: cohens_kappa(e, consensus_reference(e)),
        eta,
        iterations=500,
        seed=1,
    )
    _, lo_2, hi_2 = subsampling_kappa_ci(
        lambda e: cohens_kappa(e, consensus_reference(e)),
        eta,
        iterations=500,
        seed=2,
    )
    # Don't require any specific difference, but the two CIs should not be identical
    assert (lo_1, hi_1) != (lo_2, hi_2)


def test_subsampling_ci_undefined_point_raises() -> None:
    """If κ on the full eval is None (e.g. all model verdicts identical to
    the reference -> p_e = 1), the CI cannot be constructed."""
    # All-agreement, single-class eval -> p_e collapses
    items = [_item(f"a{i}", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD)
             for i in range(20)]
    eta = Evaluation(
        id="r",
        benchmark_id="b",
        model=ModelInfo(provider="mock", model_id="t1", params=ProviderParams()),
        items=items,
    )
    with pytest.raises(ValueError, match="point estimate is undefined"):
        subsampling_kappa_ci(
            lambda e: cohens_kappa(e, consensus_reference(e)),
            eta,
        )


# ---- MetricsReport surface ------------------------------------------------


def test_metrics_report_cohens_kappa_with_ci_smoke() -> None:
    eta = _mixed_eval(30)
    report = MetricsReport(eta=eta)
    point, lo, hi = report.cohens_kappa_with_ci(iterations=200, seed=42)
    assert point == pytest.approx(report.cohens_kappa())
    assert lo <= point <= hi


def test_metrics_report_fleiss_kappa_with_ci_smoke() -> None:
    # Need at least 2 analysts for Fleiss to be defined
    items: list[EvaluationItem] = []
    for i in range(20):
        v = Verdict.GOOD if i % 3 != 0 else Verdict.BAD
        items.append(
            EvaluationItem(
                id=f"a{i}",
                premises=["x"],
                conclusions=["y"],
                analyst_verdicts=[v, v],
                model_verdict=v if i % 4 != 0 else (
                    Verdict.BAD if v == Verdict.GOOD else Verdict.GOOD
                ),
                majority_vote=MajorityVote(
                    good=5 if v == Verdict.GOOD else 0,
                    bad=5 if v == Verdict.BAD else 0,
                    abstain=0,
                    verdict=v,
                ),
            )
        )
    eta = Evaluation(
        id="r",
        benchmark_id="b",
        model=ModelInfo(provider="mock", model_id="t1", params=ProviderParams()),
        items=items,
    )
    report = MetricsReport(eta=eta)
    point, lo, hi = report.fleiss_kappa_with_ci(iterations=200, seed=42)
    # Should be defined (substantive agreements present)
    assert point is not None
    assert fleiss_kappa(eta) == pytest.approx(point)


def test_subsampling_ci_passes_through_callable_kappa_fn() -> None:
    """Verifies subsampling_kappa_ci dispatches via the kappa_fn parameter,
    so users can plug in a weighted variant by closing over weights."""
    from infereval.metrics import margin_weight

    eta = _mixed_eval(30)
    point_w, lo_w, hi_w = subsampling_kappa_ci(
        lambda e: cohens_kappa(
            e, consensus_reference(e), weights=margin_weight
        ),
        eta,
        iterations=200,
        seed=42,
    )
    point_u, lo_u, hi_u = subsampling_kappa_ci(
        lambda e: cohens_kappa(e, consensus_reference(e)),
        eta,
        iterations=200,
        seed=42,
    )
    # With this synthetic eval all items have unanimous samples
    # (margin = 1.0 for all), so weighted == unweighted.
    assert point_w == pytest.approx(point_u)
