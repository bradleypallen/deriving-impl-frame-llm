"""Tests for ``infereval.metrics.cohens_kappa``.

Hand-computed cases plus the edge cases the paper flags:

- :math:`S(\\eta, r)` empty -> None.
- :math:`p_e = 1` (degenerate) -> None.
- Perfect agreement on non-degenerate distribution -> 1.0.
- Chance-level agreement (matches by random) -> 0.0.
"""

from __future__ import annotations

import math

import pytest

from infereval.metrics import (
    analyst_reference,
    cohens_kappa,
    consensus_reference,
)
from infereval.types import Verdict

from ..conftest import build_evaluation

G = Verdict.GOOD
B = Verdict.BAD
A = Verdict.ABSTAIN


# ---- Perfect agreement -----------------------------------------------------


class TestPerfectAgreement:
    def test_perfect_against_consensus(self) -> None:
        # 3 good, 1 bad, all match
        eta = build_evaluation(rows=[([G], G), ([G], G), ([G], G), ([B], B)])
        assert cohens_kappa(eta, consensus_reference(eta)) == pytest.approx(1.0)

    def test_perfect_against_single_analyst(self) -> None:
        eta = build_evaluation(rows=[([G, B], G), ([B, G], B), ([G, G], G)])
        # M matches analyst 0 exactly
        assert cohens_kappa(eta, analyst_reference(eta, 0)) == pytest.approx(1.0)


# ---- Hand-computed examples -----------------------------------------------


class TestHandComputed:
    def test_two_class_chance_level(self) -> None:
        # 2 good 2 bad on each side, but only 2 of 4 match -> chance level
        # M:      G G B B
        # Ref:    G B G B
        # matches: 1 0 0 1 -> 2/4 agreement
        # p_M(good) = 0.5, p_M(bad) = 0.5
        # p_r(good) = 0.5, p_r(bad) = 0.5
        # p_o = 0.5
        # p_e = 0.5*0.5 + 0.5*0.5 = 0.5
        # kappa = (0.5 - 0.5) / (1 - 0.5) = 0
        eta = build_evaluation(rows=[([G], G), ([B], G), ([G], B), ([B], B)])
        assert cohens_kappa(eta, consensus_reference(eta)) == pytest.approx(0.0)

    def test_above_chance(self) -> None:
        # 3 of 4 match; non-uniform marginals
        # M:    G G G B
        # Ref:  G G B B
        # p_o = 3/4 = 0.75
        # p_M(good) = 0.75, p_M(bad) = 0.25
        # p_r(good) = 0.5, p_r(bad) = 0.5
        # p_e = 0.75*0.5 + 0.25*0.5 = 0.375 + 0.125 = 0.5
        # kappa = (0.75 - 0.5) / (1 - 0.5) = 0.25 / 0.5 = 0.5
        eta = build_evaluation(rows=[([G], G), ([G], G), ([B], G), ([B], B)])
        assert cohens_kappa(eta, consensus_reference(eta)) == pytest.approx(0.5)

    def test_below_chance(self) -> None:
        # Systematic disagreement: 1 of 4 match
        # M:    G G G B
        # Ref:  B B B G
        # p_o = 0/4 = 0
        # p_M(good) = 0.75, p_M(bad) = 0.25
        # p_r(good) = 0.25, p_r(bad) = 0.75
        # p_e = 0.75*0.25 + 0.25*0.75 = 0.1875 + 0.1875 = 0.375
        # kappa = (0 - 0.375) / (1 - 0.375) = -0.375 / 0.625 = -0.6
        eta = build_evaluation(rows=[([B], G), ([B], G), ([B], G), ([G], B)])
        assert cohens_kappa(eta, consensus_reference(eta)) == pytest.approx(-0.6)


# ---- Edge cases ------------------------------------------------------------


class TestEdgeCases:
    def test_empty_S_returns_none(self) -> None:
        # Every model verdict is abstain -> S empty -> None
        eta = build_evaluation(rows=[([G], A), ([B], A), ([G], A)])
        assert cohens_kappa(eta, consensus_reference(eta)) is None

    def test_reference_all_abstain_returns_none(self) -> None:
        # M substantive but consensus is always abstain (single-analyst ties not possible,
        # so simulate with 2 analysts always tied)
        eta = build_evaluation(rows=[([G, B], G), ([G, B], B), ([B, G], G)])
        assert cohens_kappa(eta, consensus_reference(eta)) is None

    def test_degenerate_p_e_one_returns_none(self) -> None:
        # All M and all reference are good -> p_e = 1
        eta = build_evaluation(rows=[([G], G), ([G], G), ([G], G)])
        assert cohens_kappa(eta, consensus_reference(eta)) is None

    def test_partial_substantive_subset(self) -> None:
        # Two abstains, two substantive -- still computable
        # M:    G B A A
        # Ref:  G B G B
        # S = {0, 1}, both match -> p_o = 1
        # p_M on S: good=0.5, bad=0.5
        # p_r on S: good=0.5, bad=0.5
        # p_e = 0.5
        # kappa = (1 - 0.5) / 0.5 = 1.0
        eta = build_evaluation(rows=[([G], G), ([B], B), ([G], A), ([B], A)])
        assert cohens_kappa(eta, consensus_reference(eta)) == pytest.approx(1.0)


# ---- Properties (bounds) --------------------------------------------------


class TestProperties:
    def test_kappa_in_minus_one_to_one(self) -> None:
        # Build random-ish evaluations and check bounds.
        seed_cases = [
            [([G], G), ([B], B), ([G], B), ([B], G)],
            [([G], G), ([G], G), ([B], B), ([G], B)],
            [([B], G), ([G], B), ([B], G), ([G], B)],
        ]
        for rows in seed_cases:
            eta = build_evaluation(rows=rows)
            k = cohens_kappa(eta, consensus_reference(eta))
            if k is not None:
                assert -1.0 - 1e-9 <= k <= 1.0 + 1e-9, (
                    f"kappa {k} out of range for rows {rows}"
                )

    def test_kappa_is_finite(self) -> None:
        eta = build_evaluation(rows=[([G], G), ([B], B), ([G], B)])
        k = cohens_kappa(eta, consensus_reference(eta))
        assert k is not None
        assert math.isfinite(k)
