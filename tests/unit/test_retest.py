"""Tests for the test-retest reliability comparator added in v0.6.0.

Covers:
- :func:`infereval.retest.compute_retest` happy path: identical runs ->
  κ = 1.0, no flips.
- Single-flip detection.
- Stability-verdict ladder rungs.
- :class:`RetestConfigMismatchError` triggers: benchmark_id /
  benchmark_hash / endorsement_config / paraphrase_variant mismatch.
- Per-item :class:`ItemDelta` shape (entropy / margin deltas).
- :func:`retest_result_to_dict` round-trip.
"""

from __future__ import annotations

import pytest

from infereval.evaluation import (
    EndorsementConfig,
    Evaluation,
    EvaluationItem,
    MajorityVote,
    ModelInfo,
    ProviderParams,
)
from infereval.retest import (
    RetestConfigMismatchError,
    compute_retest,
    retest_result_to_dict,
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
) -> EvaluationItem:
    return EvaluationItem(
        id=item_id,
        premises=["x"],
        conclusions=["y"],
        analyst_verdicts=analyst_verdicts,
        model_verdict=model_verdict,
        majority_vote=MajorityVote(
            good=good, bad=bad, abstain=abstain, verdict=model_verdict
        ),
    )


def _eval(
    items: list[EvaluationItem],
    *,
    run_id: str = "r1",
    benchmark_hash: str | None = "abc123",
    config: EndorsementConfig | None = None,
    paraphrase_variant: int = 0,
) -> Evaluation:
    return Evaluation(
        id=run_id,
        benchmark_id="bench",
        benchmark_hash=benchmark_hash,
        model=ModelInfo(provider="mock", model_id="t1", params=ProviderParams()),
        endorsement_config=config or EndorsementConfig(),
        paraphrase_variant=paraphrase_variant,
        items=items,
    )


# ---- Happy path ----------------------------------------------------------


def test_identical_runs_give_kappa_1_no_flips() -> None:
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=5, bad=0, abstain=0),
        _item("b", analyst_verdicts=[Verdict.BAD], model_verdict=Verdict.BAD,
              good=0, bad=5, abstain=0),
        _item("c", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=4, bad=1, abstain=0),
    ]
    eta_a = _eval(items, run_id="A")
    eta_b = _eval(items, run_id="B")
    result = compute_retest(eta_a, eta_b)
    assert result.n_items == 3
    assert result.n_agreements == 3
    assert result.n_disagreements == 0
    assert result.test_retest_kappa == pytest.approx(1.0)
    assert result.flipped_items == ()
    assert "stable" in result.stability_verdict
    assert result.run_a_id == "A"
    assert result.run_b_id == "B"


def test_single_flip_recorded_and_kappa_below_1() -> None:
    items_a = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=5, bad=0, abstain=0),
        _item("b", analyst_verdicts=[Verdict.BAD], model_verdict=Verdict.BAD,
              good=0, bad=5, abstain=0),
        _item("c", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=3, bad=2, abstain=0),
    ]
    items_b = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=5, bad=0, abstain=0),
        _item("b", analyst_verdicts=[Verdict.BAD], model_verdict=Verdict.BAD,
              good=0, bad=5, abstain=0),
        _item("c", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.BAD,
              good=1, bad=4, abstain=0),  # flipped from GOOD
    ]
    eta_a = _eval(items_a, run_id="A")
    eta_b = _eval(items_b, run_id="B")
    result = compute_retest(eta_a, eta_b)
    assert result.n_agreements == 2
    assert result.n_disagreements == 1
    assert len(result.flipped_items) == 1
    assert result.flipped_items[0].item_id == "c"
    assert result.flipped_items[0].verdict_a == "good"
    assert result.flipped_items[0].verdict_b == "bad"
    assert result.test_retest_kappa is not None
    assert result.test_retest_kappa < 1.0


def test_stability_verdict_ladder() -> None:
    """Exercise all three rungs by constructing controlled retests."""
    # Stable: kappa >= 0.8. We'll get kappa = 1.0 from a perfectly-matching pair.
    perfect = [
        _item(f"i{i}", analyst_verdicts=[Verdict.GOOD if i % 2 == 0 else Verdict.BAD],
              model_verdict=Verdict.GOOD if i % 2 == 0 else Verdict.BAD,
              good=5 if i % 2 == 0 else 0, bad=0 if i % 2 == 0 else 5, abstain=0)
        for i in range(10)
    ]
    result_stable = compute_retest(_eval(perfect, run_id="A"), _eval(perfect, run_id="B"))
    assert "stable" in result_stable.stability_verdict
    assert "moderately" not in result_stable.stability_verdict
    assert "unstable" not in result_stable.stability_verdict

    # Substantively unstable: flip enough to drag kappa below 0.6.
    # Start with 10 items, flip 4 of them between runs.
    items_a = [
        _item(f"i{i}", analyst_verdicts=[Verdict.GOOD if i % 2 == 0 else Verdict.BAD],
              model_verdict=Verdict.GOOD if i % 2 == 0 else Verdict.BAD,
              good=5 if i % 2 == 0 else 0, bad=0 if i % 2 == 0 else 5, abstain=0)
        for i in range(10)
    ]
    items_b = []
    for i in range(10):
        analyst = Verdict.GOOD if i % 2 == 0 else Verdict.BAD
        # First 4 items: flip; rest: keep
        model_v = (
            (Verdict.BAD if analyst == Verdict.GOOD else Verdict.GOOD)
            if i < 4
            else analyst
        )
        items_b.append(
            _item(
                f"i{i}",
                analyst_verdicts=[analyst],
                model_verdict=model_v,
                good=5 if model_v == Verdict.GOOD else 0,
                bad=5 if model_v == Verdict.BAD else 0,
                abstain=0,
            )
        )
    result_unstable = compute_retest(
        _eval(items_a, run_id="A"), _eval(items_b, run_id="B")
    )
    # Flip rate is 4/10 = 40%
    assert result_unstable.flip_rate == pytest.approx(0.4)
    # Kappa here is computed over the 10 (verdict_a, verdict_b) pairs:
    # 6 stay-good/stay-bad agreements, 4 flips. Cohen's κ on the verdict
    # columns -> roughly 0.2; landing in "substantively unstable".
    assert result_unstable.test_retest_kappa is not None
    assert result_unstable.test_retest_kappa < 0.6
    assert "unstable" in result_unstable.stability_verdict


# ---- Compatibility check errors -----------------------------------------


def test_benchmark_id_mismatch_raises() -> None:
    eta_a = _eval([_item("a", analyst_verdicts=[Verdict.GOOD],
                         model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0)],
                  run_id="A")
    items_b = [_item("a", analyst_verdicts=[Verdict.GOOD],
                     model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0)]
    eta_b = Evaluation(
        id="B",
        benchmark_id="OTHER-BENCH",
        benchmark_hash="abc123",
        model=ModelInfo(provider="mock", model_id="t1", params=ProviderParams()),
        items=items_b,
    )
    with pytest.raises(RetestConfigMismatchError, match="benchmark_id"):
        compute_retest(eta_a, eta_b)


def test_benchmark_hash_mismatch_raises() -> None:
    items = [_item("a", analyst_verdicts=[Verdict.GOOD],
                   model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0)]
    eta_a = _eval(items, run_id="A", benchmark_hash="aaaaaa")
    eta_b = _eval(items, run_id="B", benchmark_hash="bbbbbb")
    with pytest.raises(RetestConfigMismatchError, match="benchmark_hash"):
        compute_retest(eta_a, eta_b)


def test_endorsement_config_mismatch_raises() -> None:
    items = [_item("a", analyst_verdicts=[Verdict.GOOD],
                   model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0)]
    eta_a = _eval(items, run_id="A", config=EndorsementConfig(n_samples=5))
    eta_b = _eval(items, run_id="B", config=EndorsementConfig(n_samples=3))
    with pytest.raises(RetestConfigMismatchError, match="endorsement_config"):
        compute_retest(eta_a, eta_b)


def test_paraphrase_variant_mismatch_raises() -> None:
    items = [_item("a", analyst_verdicts=[Verdict.GOOD],
                   model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0)]
    eta_a = _eval(items, run_id="A", paraphrase_variant=0)
    eta_b = _eval(items, run_id="B", paraphrase_variant=1)
    with pytest.raises(RetestConfigMismatchError, match="paraphrase_variant"):
        compute_retest(eta_a, eta_b)


# ---- Per-item deltas + dict serialization -------------------------------


def test_item_deltas_record_entropy_and_margin_per_run() -> None:
    # Run A: confident agree (5/0/0). Run B: thin agree (3/2/0).
    items_a = [_item("a", analyst_verdicts=[Verdict.GOOD],
                     model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0)]
    items_b = [_item("a", analyst_verdicts=[Verdict.GOOD],
                     model_verdict=Verdict.GOOD, good=3, bad=2, abstain=0)]
    result = compute_retest(_eval(items_a, run_id="A"), _eval(items_b, run_id="B"))
    assert len(result.item_deltas) == 1
    delta = result.item_deltas[0]
    assert delta.item_id == "a"
    assert delta.verdict_a == "good" and delta.verdict_b == "good"  # not flipped
    assert delta.margin_a == 1.0
    assert delta.margin_b == pytest.approx(0.2)
    assert delta.margin_delta == pytest.approx(0.8)
    assert delta.entropy_b > delta.entropy_a  # thin distribution is higher entropy
    assert delta.entropy_delta > 0


def test_dict_serialization_round_trip() -> None:
    items = [
        _item("a", analyst_verdicts=[Verdict.GOOD], model_verdict=Verdict.GOOD,
              good=5, bad=0, abstain=0),
    ]
    result = compute_retest(_eval(items, run_id="A"), _eval(items, run_id="B"))
    d = retest_result_to_dict(result)
    assert d["schema_version"] == "1.0"
    assert d["benchmark_id"] == "bench"
    assert d["n_items"] == 1
    assert d["test_retest_kappa"] is None  # single item, all-GOOD -> p_e = 1
    assert d["agreement_rate"] == 1.0
    assert d["flipped_items"] == []
    assert len(d["item_deltas"]) == 1
    assert "stability_verdict" in d
    assert "framework_version" in d


# ---- Item-id intersection ------------------------------------------------


def test_item_id_intersection_runs_over_common_items_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When one run is missing items present in the other, the comparison
    runs over the intersection with a logged warning."""
    items_a = [
        _item(f"i{i}", analyst_verdicts=[Verdict.GOOD],
              model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0)
        for i in range(3)
    ]
    items_b = [
        _item("i0", analyst_verdicts=[Verdict.GOOD],
              model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0),
        _item("i1", analyst_verdicts=[Verdict.GOOD],
              model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0),
        # i2 missing; new item i3 instead
        _item("i3", analyst_verdicts=[Verdict.GOOD],
              model_verdict=Verdict.GOOD, good=5, bad=0, abstain=0),
    ]
    caplog.clear()
    import logging
    caplog.set_level(logging.WARNING, logger="infereval.retest")
    result = compute_retest(_eval(items_a, run_id="A"), _eval(items_b, run_id="B"))
    assert result.n_items == 2  # i0, i1 common
    assert "only-in-A" in caplog.text
