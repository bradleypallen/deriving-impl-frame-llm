"""Tests for ``infereval.endorsement.majority_vote``.

Tie rules locked from M3 plan:

1. Empty vote list -> abstain.
2. Sole majority wins, no tie.
3. ABSTAIN-in-tie always wins (conservative).
4. Pure GOOD/BAD tie: apply tie_break (default abstain).
5. Three-way tie at n=3 has abstain in it, so abstain wins.
"""

from __future__ import annotations

import pytest

from infereval.endorsement import majority_vote
from infereval.types import Verdict


class TestEmptyAndSingle:
    def test_empty_returns_abstain_no_tie(self) -> None:
        assert majority_vote([]) == (Verdict.ABSTAIN, False)

    def test_single_verdict_wins(self) -> None:
        assert majority_vote([Verdict.GOOD]) == (Verdict.GOOD, False)
        assert majority_vote([Verdict.BAD]) == (Verdict.BAD, False)
        assert majority_vote([Verdict.ABSTAIN]) == (Verdict.ABSTAIN, False)


class TestSoleMajority:
    def test_clean_good_majority(self) -> None:
        verdicts = [Verdict.GOOD] * 4 + [Verdict.BAD]
        assert majority_vote(verdicts) == (Verdict.GOOD, False)

    def test_clean_bad_majority(self) -> None:
        verdicts = [Verdict.BAD] * 3 + [Verdict.ABSTAIN, Verdict.GOOD]
        assert majority_vote(verdicts) == (Verdict.BAD, False)

    def test_clean_abstain_majority(self) -> None:
        verdicts = [Verdict.ABSTAIN] * 3 + [Verdict.GOOD]
        assert majority_vote(verdicts) == (Verdict.ABSTAIN, False)


class TestAbstainAlwaysWinsTies:
    def test_two_way_tie_good_abstain(self) -> None:
        # 2 good, 2 abstain -> abstain (since abstain is in the tied set)
        assert majority_vote([Verdict.GOOD, Verdict.GOOD, Verdict.ABSTAIN, Verdict.ABSTAIN]) == (
            Verdict.ABSTAIN,
            True,
        )

    def test_two_way_tie_bad_abstain(self) -> None:
        assert majority_vote([Verdict.BAD, Verdict.BAD, Verdict.ABSTAIN, Verdict.ABSTAIN]) == (
            Verdict.ABSTAIN,
            True,
        )

    def test_three_way_tie_at_n_three(self) -> None:
        # 1 good, 1 bad, 1 abstain -> abstain (in tied set)
        assert majority_vote([Verdict.GOOD, Verdict.BAD, Verdict.ABSTAIN]) == (
            Verdict.ABSTAIN,
            True,
        )

    def test_three_way_tie_at_n_six(self) -> None:
        # 2 each -> abstain
        verdicts = [Verdict.GOOD, Verdict.GOOD, Verdict.BAD, Verdict.BAD, Verdict.ABSTAIN, Verdict.ABSTAIN]
        assert majority_vote(verdicts) == (Verdict.ABSTAIN, True)


class TestPureGoodBadTie:
    """Tied between GOOD and BAD only (no ABSTAIN in tied set)."""

    @pytest.fixture
    def good_bad_tie(self) -> list[Verdict]:
        return [Verdict.GOOD, Verdict.BAD]

    def test_default_tie_break_is_abstain(self, good_bad_tie: list[Verdict]) -> None:
        assert majority_vote(good_bad_tie) == (Verdict.ABSTAIN, True)

    def test_tie_break_good(self, good_bad_tie: list[Verdict]) -> None:
        assert majority_vote(good_bad_tie, tie_break="good") == (Verdict.GOOD, True)

    def test_tie_break_bad(self, good_bad_tie: list[Verdict]) -> None:
        assert majority_vote(good_bad_tie, tie_break="bad") == (Verdict.BAD, True)

    def test_tie_break_first_picks_first_appearance(self) -> None:
        # First appearance of GOOD is at index 0
        assert majority_vote([Verdict.GOOD, Verdict.BAD], tie_break="first") == (
            Verdict.GOOD,
            True,
        )
        # First appearance of BAD is at index 0
        assert majority_vote([Verdict.BAD, Verdict.GOOD], tie_break="first") == (
            Verdict.BAD,
            True,
        )

    def test_tie_break_first_with_interleaving(self) -> None:
        # [GOOD, BAD, GOOD, BAD] -> 2 each -> first GOOD
        assert majority_vote(
            [Verdict.GOOD, Verdict.BAD, Verdict.GOOD, Verdict.BAD], tie_break="first"
        ) == (Verdict.GOOD, True)


class TestRealisticScenarios:
    """Cases that arise in actual evaluation runs."""

    def test_four_good_one_unparseable(self) -> None:
        # Typical clean case: model is consistent, one parse failure
        verdicts = [Verdict.GOOD] * 4 + [Verdict.ABSTAIN]
        v, tie = majority_vote(verdicts)
        assert v == Verdict.GOOD
        assert not tie

    def test_all_abstain(self) -> None:
        # Provider failed every sample, or every response was unparseable
        verdicts = [Verdict.ABSTAIN] * 5
        assert majority_vote(verdicts) == (Verdict.ABSTAIN, False)

    def test_three_good_two_bad(self) -> None:
        # n=5 with a clear good majority
        verdicts = [Verdict.GOOD] * 3 + [Verdict.BAD] * 2
        assert majority_vote(verdicts) == (Verdict.GOOD, False)
