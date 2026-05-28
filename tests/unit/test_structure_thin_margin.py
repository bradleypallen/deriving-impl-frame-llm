"""Tests for the thin-margin agreement check added in v0.6.0.

A thin-margin agreement is an item where the model agrees with the
analyst consensus but the agreement is supported by a thin majority
over the sampled verdicts. These are agreements that could flip on a
re-run; surfacing them prevents the headline κ from over-stating the
reliability of the measurement.
"""

from __future__ import annotations

from infereval.evaluation import (
    Evaluation,
    EvaluationItem,
    MajorityVote,
    ModelInfo,
    ProviderParams,
)
from infereval.structure import (
    DEFAULT_THIN_MARGIN_THRESHOLD,
    thin_margin_agreement_check,
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


def test_confident_agreement_is_satisfying_not_an_anomaly() -> None:
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=5, bad=0, abstain=0),
    ]
    check = thin_margin_agreement_check(_eval(items))
    assert check.name == "thin_margin_agreement"
    assert check.items_checked == 1
    assert check.items_satisfying == 1
    assert check.anomalies == ()


def test_thin_agreement_flagged_as_anomaly() -> None:
    # 3/2/0: margin = 0.2 < 0.4 threshold
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=3, bad=2, abstain=0),
    ]
    check = thin_margin_agreement_check(_eval(items))
    assert check.items_checked == 1
    assert check.items_satisfying == 0
    assert len(check.anomalies) == 1
    anomaly = check.anomalies[0]
    assert anomaly.item_id == "a"
    assert "margin" in anomaly.actual
    assert "could flip" in anomaly.explanation


def test_disagreement_not_in_check_universe() -> None:
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.BAD,
              good=0, bad=5, abstain=0),  # disagreement, even though confident
        _item("b", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=5, bad=0, abstain=0),  # confident agreement
    ]
    check = thin_margin_agreement_check(_eval(items))
    # Only the agreement counts as "checked"
    assert check.items_checked == 1
    assert check.items_satisfying == 1


def test_abstain_consensus_not_in_check_universe() -> None:
    # Analyst gave a single abstain -> consensus is abstain (non-substantive)
    items = [
        _item("a", analyst_verdicts=[Verdict.ABSTAIN], model_verdict=Verdict.GOOD,
              good=3, bad=2, abstain=0),
    ]
    check = thin_margin_agreement_check(_eval(items))
    assert check.items_checked == 0


def test_model_abstain_not_in_check_universe() -> None:
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.ABSTAIN,
              good=0, bad=0, abstain=5),
    ]
    check = thin_margin_agreement_check(_eval(items))
    assert check.items_checked == 0


def test_tie_broken_agreement_is_thin() -> None:
    # 2/2/1 tie-break to GOOD: margin = 0, definitely thin
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=2, bad=2, abstain=1, tie_broken=True),
    ]
    check = thin_margin_agreement_check(_eval(items))
    assert check.items_checked == 1
    assert check.items_satisfying == 0
    assert len(check.anomalies) == 1
    assert "tie-broken" in check.anomalies[0].actual


def test_threshold_override() -> None:
    # 3/2/0: margin = 0.2. With threshold=0.1 it's satisfying; with 0.5 it's not.
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=3, bad=2, abstain=0),
    ]
    loose = thin_margin_agreement_check(_eval(items), threshold=0.1)
    assert loose.items_satisfying == 1
    assert loose.anomalies == ()
    strict = thin_margin_agreement_check(_eval(items), threshold=0.5)
    assert strict.items_satisfying == 0
    assert len(strict.anomalies) == 1


def test_default_threshold_matches_documented_value() -> None:
    assert DEFAULT_THIN_MARGIN_THRESHOLD == 0.4


def test_mixed_corpus_partitions_correctly() -> None:
    items = [
        _item("confident-agree", analyst_verdicts=[Verdict.GOOD],
              model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0),
        _item("thin-agree", analyst_verdicts=[Verdict.BAD],
              model_verdict=Verdict.BAD, good=0, bad=3, abstain=2),  # margin 0.2
        _item("disagree", analyst_verdicts=[Verdict.GOOD],
              model_verdict=Verdict.BAD, good=0, bad=5, abstain=0),
        _item("confident-agree-2", analyst_verdicts=[Verdict.GOOD],
              model_verdict=Verdict.GOOD, good=4, bad=1, abstain=0),  # margin 0.6
    ]
    check = thin_margin_agreement_check(_eval(items))
    assert check.items_checked == 3  # disagree excluded
    assert check.items_satisfying == 2
    assert len(check.anomalies) == 1
    assert check.anomalies[0].item_id == "thin-agree"
    assert check.rate == 2 / 3
