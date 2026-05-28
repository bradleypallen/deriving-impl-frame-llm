"""Tests for the per-item verdict-distribution surface added in v0.6.0.

Covers:
- :class:`infereval.metrics.VerdictDistribution` properties (n_samples,
  entropy, margin) on synthetic 5-sample inputs.
- :func:`infereval.metrics.verdict_distribution` round-trip from a real
  :class:`~infereval.evaluation.EvaluationItem` with a populated
  ``majority_vote`` field, and the fallback path that counts raw
  ``samples`` when ``majority_vote`` is ``None``.
- :class:`infereval.metrics.AggregateDispersion` aggregation logic.
- :meth:`infereval.metrics.MetricsReport.verdict_distributions` and
  :meth:`MetricsReport.aggregate_dispersion_summary`.
- :meth:`MetricsReport.to_dict` includes the new
  ``verdict_distributions`` and ``aggregate_dispersion`` blocks by
  default (the ``report_verdict_distribution = true`` locked default).
"""

from __future__ import annotations

import math

import pytest

from infereval.evaluation import (
    Evaluation,
    EvaluationItem,
    MajorityVote,
    ModelInfo,
    ProviderParams,
    SampleRecord,
)
from infereval.metrics import (
    AggregateDispersion,
    MetricsReport,
    VerdictDistribution,
    margin_weight,
    verdict_distribution,
)
from infereval.types import Verdict

# ---- VerdictDistribution intrinsic properties --------------------------------


def test_verdict_distribution_unanimous_good_full_margin_zero_entropy() -> None:
    d = VerdictDistribution(good=5, bad=0, abstain=0, verdict=Verdict.GOOD)
    assert d.n_samples == 5
    assert d.margin == 1.0
    assert d.entropy == 0.0


def test_verdict_distribution_unanimous_bad_full_margin_zero_entropy() -> None:
    d = VerdictDistribution(good=0, bad=5, abstain=0, verdict=Verdict.BAD)
    assert d.n_samples == 5
    assert d.margin == 1.0
    assert d.entropy == 0.0


def test_verdict_distribution_unanimous_abstain_full_margin_zero_entropy() -> None:
    d = VerdictDistribution(good=0, bad=0, abstain=5, verdict=Verdict.ABSTAIN)
    assert d.n_samples == 5
    assert d.margin == 1.0
    assert d.entropy == 0.0


def test_verdict_distribution_thin_margin_3_2_0() -> None:
    d = VerdictDistribution(good=3, bad=2, abstain=0, verdict=Verdict.GOOD)
    assert d.n_samples == 5
    assert d.margin == pytest.approx(0.2)
    # Entropy of {0.6, 0.4} normalised by log(3)
    expected = -(0.6 * math.log(0.6) + 0.4 * math.log(0.4)) / math.log(3)
    assert d.entropy == pytest.approx(expected)


def test_verdict_distribution_thin_margin_3_2_1_with_abstain() -> None:
    d = VerdictDistribution(good=3, bad=2, abstain=1, verdict=Verdict.GOOD)
    assert d.n_samples == 6
    assert d.margin == pytest.approx((3 - 2) / 6)
    p = [3 / 6, 2 / 6, 1 / 6]
    expected = -sum(x * math.log(x) for x in p) / math.log(3)
    assert d.entropy == pytest.approx(expected)


def test_verdict_distribution_tie_yields_zero_margin() -> None:
    # 2/2/1 tie at the top, even after tie-break resolves to GOOD
    d = VerdictDistribution(
        good=2, bad=2, abstain=1, verdict=Verdict.GOOD, tie_broken=True
    )
    assert d.margin == 0.0
    assert d.tie_broken is True


def test_verdict_distribution_uniform_max_entropy() -> None:
    # 3/3/3 distribution: entropy should hit 1.0 exactly after log(3) normalisation
    d = VerdictDistribution(
        good=3, bad=3, abstain=3, verdict=Verdict.ABSTAIN, tie_broken=True
    )
    assert d.entropy == pytest.approx(1.0)
    assert d.margin == 0.0


def test_verdict_distribution_empty_handled() -> None:
    d = VerdictDistribution(good=0, bad=0, abstain=0, verdict=Verdict.ABSTAIN)
    assert d.n_samples == 0
    assert d.margin == 0.0
    assert d.entropy == 0.0


# ---- verdict_distribution() builder ----------------------------------------


def _make_item_with_mv(
    item_id: str,
    *,
    good: int,
    bad: int,
    abstain: int,
    verdict: Verdict,
    tie_broken: bool = False,
) -> EvaluationItem:
    """EvaluationItem with a populated MajorityVote (the standard case)."""
    return EvaluationItem(
        id=item_id,
        premises=["x"],
        conclusions=["y"],
        analyst_verdicts=[verdict],
        model_verdict=verdict,
        majority_vote=MajorityVote(
            good=good,
            bad=bad,
            abstain=abstain,
            verdict=verdict,
            tie_broken=tie_broken,
        ),
    )


def _make_item_with_samples_only(
    item_id: str,
    *,
    sample_verdicts: list[Verdict],
    model_verdict: Verdict,
) -> EvaluationItem:
    """EvaluationItem with samples but no MajorityVote (the fallback path)."""
    return EvaluationItem(
        id=item_id,
        premises=["x"],
        conclusions=["y"],
        analyst_verdicts=[model_verdict],
        model_verdict=model_verdict,
        samples=[
            SampleRecord(
                sample_index=i,
                raw_response=v.value,
                parsed_verdict=v,
            )
            for i, v in enumerate(sample_verdicts)
        ],
    )


def test_verdict_distribution_reads_majority_vote_when_present() -> None:
    item = _make_item_with_mv(
        "row-0", good=4, bad=1, abstain=0, verdict=Verdict.GOOD
    )
    d = verdict_distribution(item)
    assert d.good == 4 and d.bad == 1 and d.abstain == 0
    assert d.verdict == Verdict.GOOD
    assert d.tie_broken is False


def test_verdict_distribution_propagates_tie_broken_flag() -> None:
    item = _make_item_with_mv(
        "row-0", good=2, bad=2, abstain=1, verdict=Verdict.ABSTAIN, tie_broken=True
    )
    d = verdict_distribution(item)
    assert d.tie_broken is True
    assert d.margin == 0.0


def test_verdict_distribution_falls_back_to_samples_when_no_mv() -> None:
    item = _make_item_with_samples_only(
        "row-0",
        sample_verdicts=[
            Verdict.GOOD,
            Verdict.GOOD,
            Verdict.GOOD,
            Verdict.BAD,
            Verdict.ABSTAIN,
        ],
        model_verdict=Verdict.GOOD,
    )
    d = verdict_distribution(item)
    assert d.good == 3 and d.bad == 1 and d.abstain == 1
    assert d.verdict == Verdict.GOOD
    # No MajorityVote to source the tie_broken flag from
    assert d.tie_broken is False


def test_verdict_distribution_empty_samples_and_no_mv() -> None:
    item = EvaluationItem(
        id="row-0",
        premises=["x"],
        conclusions=["y"],
        analyst_verdicts=[Verdict.GOOD],
        model_verdict=Verdict.GOOD,
    )
    d = verdict_distribution(item)
    assert d.n_samples == 0
    assert d.entropy == 0.0
    assert d.margin == 0.0


# ---- margin_weight ---------------------------------------------------------


def test_margin_weight_matches_distribution_margin() -> None:
    item = _make_item_with_mv(
        "row-0", good=4, bad=1, abstain=0, verdict=Verdict.GOOD
    )
    assert margin_weight(item) == pytest.approx(0.6)  # (4-1)/5


def test_margin_weight_zero_for_tied_items() -> None:
    item = _make_item_with_mv(
        "row-0", good=2, bad=2, abstain=1, verdict=Verdict.ABSTAIN, tie_broken=True
    )
    assert margin_weight(item) == 0.0


# ---- MetricsReport.verdict_distributions / aggregate_dispersion_summary ----


def _eval_with_items(items: list[EvaluationItem]) -> Evaluation:
    return Evaluation(
        id="test-run",
        benchmark_id="test-bench",
        model=ModelInfo(provider="mock", model_id="t1", params=ProviderParams()),
        items=items,
    )


def test_metrics_report_verdict_distributions_keys_match_item_ids() -> None:
    items = [
        _make_item_with_mv("a", good=5, bad=0, abstain=0, verdict=Verdict.GOOD),
        _make_item_with_mv("b", good=3, bad=2, abstain=0, verdict=Verdict.GOOD),
        _make_item_with_mv("c", good=0, bad=4, abstain=1, verdict=Verdict.BAD),
    ]
    report = MetricsReport(eta=_eval_with_items(items))
    dists = report.verdict_distributions
    assert set(dists.keys()) == {"a", "b", "c"}
    assert dists["a"].margin == 1.0
    assert dists["b"].margin == pytest.approx(0.2)
    assert dists["c"].verdict == Verdict.BAD


def test_aggregate_dispersion_summary_counts_thin_and_tied() -> None:
    items = [
        _make_item_with_mv("a", good=5, bad=0, abstain=0, verdict=Verdict.GOOD),
        _make_item_with_mv("b", good=3, bad=2, abstain=0, verdict=Verdict.GOOD),  # thin
        _make_item_with_mv(
            "c", good=2, bad=2, abstain=1, verdict=Verdict.ABSTAIN, tie_broken=True
        ),  # thin AND tie-broken
        _make_item_with_mv("d", good=4, bad=1, abstain=0, verdict=Verdict.GOOD),
    ]
    report = MetricsReport(eta=_eval_with_items(items))
    agg = report.aggregate_dispersion_summary(thin_margin_threshold=0.4)
    assert isinstance(agg, AggregateDispersion)
    assert agg.n_items == 4
    # Thin = margin < 0.4: b (0.2), c (0.0)
    assert agg.n_thin_margin == 2
    assert agg.fraction_thin_margin == pytest.approx(0.5)
    assert agg.n_tie_broken == 1
    # mean_margin = (1.0 + 0.2 + 0.0 + 0.6) / 4 = 0.45
    assert agg.mean_margin == pytest.approx(0.45)


def test_aggregate_dispersion_summary_empty_eval() -> None:
    report = MetricsReport(eta=_eval_with_items([]))
    agg = report.aggregate_dispersion_summary()
    assert agg.n_items == 0
    assert agg.mean_entropy == 0.0
    assert agg.mean_margin == 0.0
    assert agg.n_thin_margin == 0
    assert agg.fraction_thin_margin == 0.0
    assert agg.n_tie_broken == 0


def test_to_dict_includes_verdict_distributions_by_default() -> None:
    items = [
        _make_item_with_mv("a", good=5, bad=0, abstain=0, verdict=Verdict.GOOD),
        _make_item_with_mv("b", good=3, bad=2, abstain=0, verdict=Verdict.GOOD),
    ]
    report = MetricsReport(eta=_eval_with_items(items))
    out = report.to_dict()
    assert "verdict_distributions" in out
    assert "aggregate_dispersion" in out
    assert set(out["verdict_distributions"].keys()) == {"a", "b"}
    assert out["verdict_distributions"]["b"]["margin"] == pytest.approx(0.2)
    assert out["aggregate_dispersion"]["n_thin_margin"] == 1


def test_to_dict_can_suppress_verdict_distributions() -> None:
    items = [
        _make_item_with_mv("a", good=5, bad=0, abstain=0, verdict=Verdict.GOOD),
    ]
    report = MetricsReport(eta=_eval_with_items(items))
    out = report.to_dict(include_verdict_distributions=False)
    assert "verdict_distributions" not in out
    assert "aggregate_dispersion" not in out
    # Pre-0.6 keys still present
    assert "n" in out
    assert "coverage" in out
    assert "cohens_kappa_consensus" in out
