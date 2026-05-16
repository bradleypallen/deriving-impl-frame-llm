"""Tests for ``infereval.metrics`` basics: coverage, consensus, substantive index."""

from __future__ import annotations

import pytest

from infereval.metrics import (
    SUBSTANTIVE,
    analyst_reference,
    consensus_reference,
    consensus_verdict,
    coverage,
    coverage_analyst,
    coverage_per_analyst,
    substantive_index,
)
from infereval.types import Verdict

from ..conftest import build_evaluation

G = Verdict.GOOD
B = Verdict.BAD
A = Verdict.ABSTAIN


# ---- Coverage --------------------------------------------------------------


class TestCoverage:
    def test_all_substantive_yields_one(self) -> None:
        eta = build_evaluation(rows=[([G], G), ([G], B), ([B], B)])
        assert coverage(eta) == 1.0

    def test_all_abstain_yields_zero(self) -> None:
        eta = build_evaluation(rows=[([G], A), ([B], A)])
        assert coverage(eta) == 0.0

    def test_half_yields_half(self) -> None:
        eta = build_evaluation(rows=[([G], G), ([G], A), ([G], B), ([G], A)])
        assert coverage(eta) == 0.5

    def test_empty_yields_zero(self) -> None:
        eta = build_evaluation(rows=[])
        assert coverage(eta) == 0.0

    def test_coverage_analyst_index(self) -> None:
        eta = build_evaluation(rows=[([G, A], G), ([B, B], B), ([A, G], G)])
        assert coverage_analyst(eta, 0) == 2 / 3  # row-0,1 substantive
        assert coverage_analyst(eta, 1) == 2 / 3  # row-1,2 substantive

    def test_coverage_per_analyst_list(self) -> None:
        eta = build_evaluation(rows=[([G, A], G), ([B, B], B), ([A, G], G)])
        assert coverage_per_analyst(eta) == [2 / 3, 2 / 3]

    def test_coverage_per_analyst_empty(self) -> None:
        eta = build_evaluation(rows=[])
        assert coverage_per_analyst(eta) == []


# ---- consensus_verdict ----------------------------------------------------


class TestConsensus:
    def test_single_analyst_good(self) -> None:
        assert consensus_verdict([G]) == G

    def test_single_analyst_bad(self) -> None:
        assert consensus_verdict([B]) == B

    def test_single_analyst_abstain(self) -> None:
        # Only one analyst, abstaining -- no strict good or bad majority
        assert consensus_verdict([A]) == A

    def test_strict_good_majority(self) -> None:
        assert consensus_verdict([G, G, B]) == G

    def test_strict_bad_majority(self) -> None:
        assert consensus_verdict([B, B, G]) == B

    def test_tie_yields_abstain(self) -> None:
        # 1 good, 1 bad -- tie -> abstain
        assert consensus_verdict([G, B]) == A
        # 2 good, 2 bad -> abstain
        assert consensus_verdict([G, G, B, B]) == A

    def test_abstains_dont_count_toward_majority(self) -> None:
        # 2 good, 0 bad, 5 abstain -> good (good > bad)
        assert consensus_verdict([G, G, A, A, A, A, A]) == G

    def test_only_abstains_yields_abstain(self) -> None:
        assert consensus_verdict([A, A, A]) == A

    def test_empty_yields_abstain(self) -> None:
        assert consensus_verdict([]) == A


# ---- ReferenceFn factories ------------------------------------------------


class TestReferenceFns:
    def test_consensus_reference_returns_per_item_consensus(self) -> None:
        eta = build_evaluation(rows=[
            ([G, G, B], G),  # consensus = good
            ([B, B, G], B),  # consensus = bad
            ([G, B], A),     # tie -> abstain
        ])
        r = consensus_reference(eta)
        assert r(0) == G
        assert r(1) == B
        assert r(2) == A

    def test_analyst_reference_returns_per_item_analyst_verdict(self) -> None:
        eta = build_evaluation(rows=[([G, B], G), ([A, G], A), ([B, A], B)])
        r0 = analyst_reference(eta, 0)
        r1 = analyst_reference(eta, 1)
        assert [r0(i) for i in range(3)] == [G, A, B]
        assert [r1(i) for i in range(3)] == [B, G, A]


# ---- Substantive index ----------------------------------------------------


class TestSubstantiveIndex:
    def test_all_substantive(self) -> None:
        eta = build_evaluation(rows=[([G], G), ([B], B), ([G], B)])
        S = substantive_index(eta, consensus_reference(eta))
        assert {0, 1, 2} == S

    def test_model_abstains_excludes_item(self) -> None:
        eta = build_evaluation(rows=[([G], G), ([G], A), ([B], B)])
        S = substantive_index(eta, consensus_reference(eta))
        assert {0, 2} == S  # row-1 excluded (model abstained)

    def test_reference_abstains_excludes_item(self) -> None:
        # Tie analyst verdicts -> consensus = abstain -> item excluded
        eta = build_evaluation(rows=[([G, B], G), ([G, G], G)])
        S = substantive_index(eta, consensus_reference(eta))
        assert {1} == S

    def test_substantive_constant_is_correct(self) -> None:
        assert frozenset({Verdict.GOOD, Verdict.BAD}) == SUBSTANTIVE
        assert Verdict.ABSTAIN not in SUBSTANTIVE


# ---- Bad index handling ---------------------------------------------------


class TestErrorPaths:
    def test_analyst_index_out_of_range(self) -> None:
        eta = build_evaluation(rows=[([G], G)])
        with pytest.raises(IndexError):
            coverage_analyst(eta, 5)
