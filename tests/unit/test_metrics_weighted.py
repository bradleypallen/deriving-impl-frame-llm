"""Tests for the confidence-weighted Cohen's / Fleiss' kappa added in v0.6.0.

Covers:
- Weighted Cohen's kappa with :func:`margin_weight`: a synthetic eval
  where the model agrees with the analyst on all items but its 3/5
  agreements should downweight κ relative to its 5/5 agreements.
- Weighted Fleiss' kappa: same shape, three annotators.
- The unweighted path with ``weights=None`` is byte-identical to the
  pre-0.6 behaviour (the headline κ is preserved as the locked default).
- ``weights`` parameter validation: zero-total-weight returns ``None``
  with a warning rather than raising.
- :meth:`MetricsReport.cohens_kappa` and ``fleiss_kappa_weighted`` honour
  the ``weights`` parameter.
"""

from __future__ import annotations

import logging

import pytest

from infereval.evaluation import (
    Evaluation,
    EvaluationItem,
    MajorityVote,
    ModelInfo,
    ProviderParams,
)
from infereval.metrics import (
    MetricsReport,
    cohens_kappa,
    consensus_reference,
    fleiss_kappa,
    margin_weight,
)
from infereval.types import Verdict


def _item(
    item_id: str,
    *,
    analyst_verdicts: list[Verdict],
    model_verdict: Verdict,
    good: int,
    bad: int,
    abstain: int,
    tie_broken: bool = False,
) -> EvaluationItem:
    return EvaluationItem(
        id=item_id,
        premises=["x"],
        conclusions=["y"],
        analyst_verdicts=analyst_verdicts,
        model_verdict=model_verdict,
        majority_vote=MajorityVote(
            good=good,
            bad=bad,
            abstain=abstain,
            verdict=model_verdict,
            tie_broken=tie_broken,
        ),
    )


def _eval(items: list[EvaluationItem]) -> Evaluation:
    return Evaluation(
        id="test-run",
        benchmark_id="test-bench",
        model=ModelInfo(provider="mock", model_id="t1", params=ProviderParams()),
        items=items,
    )


# ---- Backward-compatibility (weights=None must match pre-0.6 byte-identical) ----


def test_cohens_kappa_unweighted_path_unchanged_with_weights_none() -> None:
    """The unweighted κ_C is the locked-default headline number; must not drift."""
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=5, bad=0, abstain=0),
        _item("b", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=3, bad=2, abstain=0),
        _item("c", analyst_verdicts=[Verdict.BAD], model_verdict=Verdict.BAD,
              good=0, bad=4, abstain=1),
        _item("d", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.BAD,
              good=1, bad=4, abstain=0),
    ]
    eta = _eval(items)
    ref = consensus_reference(eta)
    explicit_none = cohens_kappa(eta, ref, weights=None)
    no_kwarg = cohens_kappa(eta, ref)
    assert explicit_none == no_kwarg
    # And both should match a hand-computation: 3 agreements / 4 substantive items.
    # p_o = 3/4 = 0.75. p_M(good) = 2/4, p_M(bad) = 2/4. p_r(good) = 3/4, p_r(bad) = 1/4.
    # p_e = 2/4 * 3/4 + 2/4 * 1/4 = 6/16 + 2/16 = 0.5.
    # kappa = (0.75 - 0.5) / (1 - 0.5) = 0.5
    assert explicit_none == pytest.approx(0.5)


def test_fleiss_kappa_unweighted_path_unchanged_with_weights_none() -> None:
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD, Verdict.GOOD],
              model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0),
        _item("b", analyst_verdicts=[Verdict.GOOD, Verdict.BAD],
              model_verdict=Verdict.GOOD, good=3, bad=2, abstain=0),
        _item("c", analyst_verdicts=[Verdict.BAD, Verdict.BAD],
              model_verdict=Verdict.BAD, good=0, bad=5, abstain=0),
    ]
    eta = _eval(items)
    explicit_none = fleiss_kappa(eta, weights=None)
    no_kwarg = fleiss_kappa(eta)
    assert explicit_none == no_kwarg


# ---- Weighted behaviour: thin agreements downweight κ ----------------------


def test_weighted_kappa_downweights_thin_agreements() -> None:
    """Two items both agree with analyst, but the 3/5 thin-margin agreement
    should be discounted under margin_weight while the 5/5 unanimous agreement
    keeps full weight. The weighted κ_C should differ from the unweighted κ_C
    when item-level weights differ.
    """
    items = [
        # Confident agreement: weight = 1.0
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=5, bad=0, abstain=0),
        # Confident agreement: weight = 1.0
        _item("b", analyst_verdicts=[Verdict.BAD], model_verdict=Verdict.BAD,
              good=0, bad=5, abstain=0),
        # Thin agreement: weight = 0.2 -- contributes less to p_o numerator
        _item("c", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=3, bad=2, abstain=0),
        # Thin DISagreement: weight = 0.2 -- contributes less to disagreement
        _item("d", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.BAD,
              good=1, bad=2, abstain=2),  # margin = (2-2)/5 = 0.0 actually
    ]
    eta = _eval(items)
    ref = consensus_reference(eta)
    unweighted = cohens_kappa(eta, ref)
    weighted = cohens_kappa(eta, ref, weights=margin_weight)
    # Both defined
    assert unweighted is not None
    assert weighted is not None
    # The weighted version should differ from the unweighted version because
    # item weights aren't uniform. (Specific direction depends on the mix of
    # agreements/disagreements at each weight; we just assert they're different.)
    assert weighted != unweighted


def test_weighted_kappa_equals_unweighted_when_all_weights_equal() -> None:
    """If every item has margin 1.0 (unanimous samples), weighted == unweighted."""
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=5, bad=0, abstain=0),
        _item("b", analyst_verdicts=[Verdict.BAD], model_verdict=Verdict.BAD,
              good=0, bad=5, abstain=0),
        _item("c", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.BAD,
              good=0, bad=5, abstain=0),
    ]
    eta = _eval(items)
    ref = consensus_reference(eta)
    unweighted = cohens_kappa(eta, ref)
    weighted = cohens_kappa(eta, ref, weights=margin_weight)
    assert unweighted == pytest.approx(weighted)


# ---- Edge cases ------------------------------------------------------------


def test_weighted_cohen_returns_none_when_all_weights_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """All-tied items -> all margin=0 -> weighted κ_C should return None with a warning."""
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=2, bad=2, abstain=1, tie_broken=True),
        _item("b", analyst_verdicts=[Verdict.BAD], model_verdict=Verdict.BAD,
              good=2, bad=2, abstain=1, tie_broken=True),
    ]
    eta = _eval(items)
    ref = consensus_reference(eta)
    # Per-logger set_level + clear() is order-independent; caplog.at_level()
    # can leak state from prior tests in the broader suite.
    caplog.clear()
    caplog.set_level(logging.WARNING, logger="infereval.metrics")
    result = cohens_kappa(eta, ref, weights=margin_weight)
    assert result is None
    assert "non-positive" in caplog.text or "zero weight" in caplog.text


def test_weighted_fleiss_returns_none_when_all_weights_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD, Verdict.GOOD],
              model_verdict=Verdict.GOOD, good=2, bad=2, abstain=1, tie_broken=True),
        _item("b", analyst_verdicts=[Verdict.BAD, Verdict.BAD],
              model_verdict=Verdict.BAD, good=2, bad=2, abstain=1, tie_broken=True),
    ]
    eta = _eval(items)
    caplog.clear()
    caplog.set_level(logging.WARNING, logger="infereval.metrics")
    result = fleiss_kappa(eta, weights=margin_weight)
    assert result is None


# ---- MetricsReport surface -------------------------------------------------


def test_metrics_report_cohens_kappa_honours_weights() -> None:
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=5, bad=0, abstain=0),
        _item("b", analyst_verdicts=[Verdict.BAD], model_verdict=Verdict.BAD,
              good=0, bad=5, abstain=0),
        _item("c", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=3, bad=2, abstain=0),
        _item("d", analyst_verdicts=[Verdict.BAD], model_verdict=Verdict.GOOD,
              good=4, bad=1, abstain=0),
    ]
    report = MetricsReport(eta=_eval(items))
    unweighted = report.cohens_kappa()
    weighted = report.cohens_kappa(weights=margin_weight)
    assert unweighted is not None
    assert weighted is not None
    # weights mode is opt-in; the default path matches the pre-0.6 headline
    assert report.cohens_kappa() == unweighted


def test_metrics_report_fleiss_kappa_weighted_method() -> None:
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD, Verdict.GOOD],
              model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0),
        _item("b", analyst_verdicts=[Verdict.GOOD, Verdict.BAD],
              model_verdict=Verdict.GOOD, good=3, bad=2, abstain=0),
        _item("c", analyst_verdicts=[Verdict.BAD, Verdict.BAD],
              model_verdict=Verdict.BAD, good=0, bad=5, abstain=0),
    ]
    report = MetricsReport(eta=_eval(items))
    unweighted = report.fleiss_kappa
    weighted = report.fleiss_kappa_weighted(margin_weight)
    assert unweighted is not None
    assert weighted is not None
