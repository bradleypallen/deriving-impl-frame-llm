"""Tests for ``infereval.metrics`` Fleiss' kappa.

Covers:

- :math:`\\kappa_F(\\eta)` with M as :math:`(m+1)`-th annotator.
- :math:`\\kappa_F^*(\\beta)` over analyst verdicts alone.
- Edge cases the paper flags: :math:`m < 2`, unanimity, all-abstain.
- Property: unanimous-and-non-degenerate annotators -> 1.0.
- Property: M as (m+1)th annotator reduces to Cohen's-style behavior at
  m=1 (paired agreement).
"""

from __future__ import annotations

import pytest

from infereval.benchmark import Benchmark
from infereval.metrics import (
    cohens_kappa,
    consensus_reference,
    fleiss_kappa,
    inter_analyst_fleiss,
)
from infereval.types import Verdict

from ..conftest import build_evaluation

G = Verdict.GOOD
B = Verdict.BAD
A = Verdict.ABSTAIN


# ---- fleiss_kappa(eta) with M as (m+1)th annotator ------------------------


class TestFleissKappa:
    def test_unanimous_non_degenerate_yields_one(self) -> None:
        # M and analyst agree on every item; both classes appear -> kappa = 1
        eta = build_evaluation(rows=[([G], G), ([G], G), ([B], B), ([B], B)])
        assert fleiss_kappa(eta) == pytest.approx(1.0)

    def test_disagreement_lowers_kappa(self) -> None:
        # M and analyst flip on one item out of 4
        eta = build_evaluation(rows=[([G], G), ([G], G), ([B], B), ([B], G)])
        k = fleiss_kappa(eta)
        assert k is not None
        assert k < 1.0

    def test_all_disagreement_yields_negative(self) -> None:
        # Perfect anti-correlation between M and analyst
        eta = build_evaluation(rows=[([G], B), ([G], B), ([B], G), ([B], G)])
        k = fleiss_kappa(eta)
        assert k is not None
        assert k < 0.0

    def test_unanimous_degenerate_yields_none(self) -> None:
        # All annotations are good -> P_bar_e = 1 -> undefined
        eta = build_evaluation(rows=[([G], G), ([G], G), ([G], G)])
        assert fleiss_kappa(eta) is None

    def test_item_with_abstain_dropped(self) -> None:
        # row-1 has an abstain -> dropped from S_F
        # Remaining: ([G], G), ([B], B), ([B], B) -- unanimous non-degenerate -> 1.0
        eta = build_evaluation(rows=[([G], G), ([A], G), ([B], B), ([B], B)])
        assert fleiss_kappa(eta) == pytest.approx(1.0)

    def test_all_items_dropped_yields_none(self) -> None:
        eta = build_evaluation(rows=[([A], G), ([A], A), ([G], A)])
        assert fleiss_kappa(eta) is None


# ---- inter_analyst_fleiss(beta or eta) ------------------------------------


class TestInterAnalystFleiss:
    def test_m_one_yields_none(self) -> None:
        # Single-analyst benchmarks have no inter-analyst comparison
        eta = build_evaluation(rows=[([G], G), ([B], B), ([G], B)])
        assert inter_analyst_fleiss(eta) is None

    def test_two_analysts_unanimous_yields_none(self) -> None:
        # m=2, both analysts agree on every item -> non-degenerate?
        # rows: ([G,G]), ([G,G]), ([B,B]), ([B,B])
        # Both classes appear, agreement is perfect.
        # Per item: n_good in {2, 0}, n_bad in {0, 2} -> P_i = 1 for all.
        # P_bar = 1.
        # p_good = 4/8 = 0.5, p_bad = 4/8 = 0.5, P_bar_e = 0.5
        # kappa = (1 - 0.5) / (1 - 0.5) = 1.0
        eta = build_evaluation(rows=[([G, G], A), ([G, G], A), ([B, B], A), ([B, B], A)])
        assert inter_analyst_fleiss(eta) == pytest.approx(1.0)

    def test_two_analysts_all_one_class_yields_none(self) -> None:
        # All annotations good -> P_bar_e = 1 -> None
        eta = build_evaluation(rows=[([G, G], A), ([G, G], A), ([G, G], A)])
        assert inter_analyst_fleiss(eta) is None

    def test_two_analysts_random_agreement(self) -> None:
        # m=2 analysts; 2 agree on good, 2 disagree, 2 agree on bad
        # rows: GG GG GB BG BB BB
        eta = build_evaluation(
            rows=[
                ([G, G], A), ([G, G], A),
                ([G, B], A), ([B, G], A),
                ([B, B], A), ([B, B], A),
            ]
        )
        k = inter_analyst_fleiss(eta)
        assert k is not None
        assert 0.0 < k < 1.0

    def test_accepts_benchmark(self, stop_sign_benchmark: Benchmark) -> None:
        # m=1 in the stop-sign benchmark -> None
        assert inter_analyst_fleiss(stop_sign_benchmark) is None


# ---- Relation between kappa_F and cohens_kappa at m=1 --------------------


class TestFleissAtMOne:
    """At m=1 (one analyst + M), Fleiss with the (m+1)th annotator is
    *not* generally equal to Cohen's against that analyst -- Cohen's
    uses asymmetric marginals (one annotator is fixed as reference),
    while Fleiss pools all annotations into one marginal distribution.

    They coincide only when the pooled marginal happens to equal each
    individual marginal, e.g. under perfect agreement on a balanced set
    or symmetric disagreement.
    """

    def test_matches_perfect_agreement(self) -> None:
        # Both kappas are 1.0 when annotators agree on every item and
        # the resulting marginal is balanced.
        eta = build_evaluation(rows=[([G], G), ([B], B), ([G], G), ([B], B)])
        kF = fleiss_kappa(eta)
        kC = cohens_kappa(eta, consensus_reference(eta))
        assert kF == kC == pytest.approx(1.0)

    def test_differs_from_cohens_on_asymmetric_marginals(self) -> None:
        # Asymmetric marginals (M skews more toward GOOD than analyst):
        # M = G G B G, analyst = G G B B -> kappa_F < kappa_C.
        eta = build_evaluation(rows=[([G], G), ([G], G), ([B], B), ([B], G)])
        kF = fleiss_kappa(eta)
        kC = cohens_kappa(eta, consensus_reference(eta))
        assert kF is not None and kC is not None
        # Cohen's = 0.5; Fleiss (pooled) ≈ 0.4667
        assert kC == pytest.approx(0.5)
        assert kF == pytest.approx(0.4666666666666667)
        assert kF < kC


# ---- Validation ----------------------------------------------------------


class TestValidation:
    def test_mismatched_tuple_lengths_raises(self) -> None:
        from infereval.metrics import _fleiss_over_tuples

        with pytest.raises(ValueError, match="same length"):
            _fleiss_over_tuples([[G, G], [G]])


# ---- Per-panel and cross-panel (Issue #36, Phase 1.4) -------------------


class TestPanelMetrics:
    """``inter_analyst_fleiss_per_panel`` and ``cross_panel_kappa``."""

    @staticmethod
    def _panelled_bench(item_verdicts: list[list[str]]) -> Benchmark:
        return Benchmark.model_validate({
            "schema_version": "1.0",
            "id": "panel-metrics-test",
            "bearers": {"p": {"expression": "P"}, "q": {"expression": "Q"}},
            "analysts": [
                {"id": "a1", "panel": "primary"},
                {"id": "a2", "panel": "primary"},
                {"id": "a3", "panel": "reviewer"},
                {"id": "a4", "panel": "reviewer"},
            ],
            "primary_panel": "primary",
            "items": [
                {
                    "id": f"i{i}",
                    "premises": ["p"],
                    "conclusions": ["q"],
                    "analyst_verdicts": v,
                }
                for i, v in enumerate(item_verdicts)
            ],
        })

    def test_per_panel_kappa_independent_of_other_panels(self) -> None:
        from infereval.metrics import inter_analyst_fleiss_per_panel

        bench = self._panelled_bench([
            ["good", "good", "good", "good"],
            ["good", "good", "bad", "bad"],
            ["bad", "bad", "bad", "bad"],
            ["good", "bad", "good", "good"],
            ["good", "good", "good", "good"],
        ])
        per_panel = inter_analyst_fleiss_per_panel(bench)
        # Reviewer panel: a3 + a4 verdicts perfectly correlated -> κ = 1.
        assert per_panel["reviewer"] == 1.0
        # Primary panel: a1 + a2 disagree on i4 -> κ between 0 and 1.
        assert per_panel["primary"] is not None
        assert 0 < per_panel["primary"] < 1

    def test_inter_analyst_fleiss_uses_primary_panel_when_panelled(self) -> None:
        from infereval.metrics import inter_analyst_fleiss, inter_analyst_fleiss_per_panel

        bench = self._panelled_bench([
            ["good", "good", "good", "good"],
            ["good", "good", "bad", "bad"],
            ["bad", "bad", "bad", "bad"],
            ["good", "bad", "good", "good"],
            ["good", "good", "good", "good"],
        ])
        per_panel = inter_analyst_fleiss_per_panel(bench)
        assert inter_analyst_fleiss(bench) == per_panel["primary"]

    def test_cross_panel_kappa_hand_calculation(self) -> None:
        from infereval.metrics import cross_panel_kappa

        # i1: both panels good (agree)
        # i2: primary good, reviewer bad (disagree)
        # i3: both bad (agree)
        # i4: primary abstain (split), reviewer good — excluded
        # i5: both good (agree)
        bench = self._panelled_bench([
            ["good", "good", "good", "good"],
            ["good", "good", "bad", "bad"],
            ["bad", "bad", "bad", "bad"],
            ["good", "bad", "good", "good"],
            ["good", "good", "good", "good"],
        ])
        kappa = cross_panel_kappa(bench)
        # Hand calc: 4 substantive pairs, 3 agree -> p_obs=0.75
        # primary marginals: good=3/4, bad=1/4
        # reviewer marginals: good=2/4, bad=2/4
        # p_exp = (0.75)(0.5) + (0.25)(0.5) = 0.5
        # κ = (0.75 - 0.5) / (1 - 0.5) = 0.5
        assert kappa is not None
        assert abs(kappa - 0.5) < 1e-9

    def test_cross_panel_kappa_returns_none_when_empty_intersection(self) -> None:
        # Every item has primary abstain -> no substantive pairs.
        from infereval.metrics import cross_panel_kappa

        bench = self._panelled_bench([
            ["good", "bad", "good", "good"],
            ["good", "bad", "bad", "bad"],
        ])
        assert cross_panel_kappa(bench) is None

    def test_cross_panel_kappa_picks_other_panel_when_only_two(self) -> None:
        from infereval.metrics import cross_panel_kappa

        # No need to specify check explicitly with 2 panels.
        bench = self._panelled_bench([
            ["good", "good", "good", "good"],
            ["good", "good", "bad", "bad"],
        ])
        # No exception; returns a value.
        result = cross_panel_kappa(bench)
        # Two items, both substantive on both panels; degenerate marginals
        # on the reviewer (all good then all bad) yield p_exp = 0.5.
        # Verified the call completes — exact value depends on marginals.
        assert isinstance(result, float)

    def test_unpanelled_benchmark_returns_empty_per_panel_dict(
        self, stop_sign_benchmark_dict: dict
    ) -> None:
        from infereval.metrics import (
            cross_panel_kappa,
            inter_analyst_fleiss_per_panel,
        )

        bench = Benchmark.model_validate(stop_sign_benchmark_dict)
        assert inter_analyst_fleiss_per_panel(bench) == {}
        # cross_panel_kappa returns None for unpanelled (warns via logger).
        assert cross_panel_kappa(bench) is None
