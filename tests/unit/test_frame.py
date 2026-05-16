"""Tests for ``infereval.frame.DerivedFrame``.

The truth-table here is Example 1 of revised.tex: rows 0-2 are endorsed
(``E_M = good``) and row 3 is rejected (``E_M = bad``). The derived frame
:math:`I_M` should contain rows 0-2 (via clause (ii)) but not row 3.
Containment (clause (i)) is checked via implications with non-empty intersection.
"""

from __future__ import annotations

import pytest

from infereval.frame import DerivedFrame
from infereval.types import Bearer, Implication, Verdict

# ---- Construction --------------------------------------------------------


class TestFromEndorsements:
    def test_constructs_with_known_bearers(
        self,
        stop_sign_bearers: dict[str, Bearer],
        stop_sign_endorsements: dict[Implication, Verdict],
    ) -> None:
        frame = DerivedFrame.from_endorsements(stop_sign_bearers, stop_sign_endorsements)
        assert set(frame.bearers) == {"sa", "ra", "n", "nr", "ba"}
        assert len(frame.queried_implications()) == 4

    def test_rejects_implication_with_unknown_bearer(
        self, stop_sign_bearers: dict[str, Bearer]
    ) -> None:
        bad = Implication.of(["sa", "unknown-bearer"], ["ra"])
        with pytest.raises(ValueError, match="unknown bearer ids"):
            DerivedFrame.from_endorsements(stop_sign_bearers, {bad: Verdict.GOOD})


# ---- Definition 3 membership iff ----------------------------------------


class TestDefinition3:
    def test_clause_ii_includes_endorsed_implications(
        self,
        stop_sign_bearers: dict[str, Bearer],
        stop_sign_endorsements: dict[Implication, Verdict],
        stop_sign_implications: dict[str, Implication],
    ) -> None:
        frame = DerivedFrame.from_endorsements(stop_sign_bearers, stop_sign_endorsements)
        # Rows 0-2: E_M = good, no premise/conclusion overlap, in I_M via (ii)
        assert frame.contains(stop_sign_implications["row-0"])
        assert frame.contains(stop_sign_implications["row-1"])
        assert frame.contains(stop_sign_implications["row-2"])

    def test_clause_ii_excludes_bad_endorsements(
        self,
        stop_sign_bearers: dict[str, Bearer],
        stop_sign_endorsements: dict[Implication, Verdict],
        stop_sign_implications: dict[str, Implication],
    ) -> None:
        frame = DerivedFrame.from_endorsements(stop_sign_bearers, stop_sign_endorsements)
        # Row 3: E_M = bad, premises and conclusions disjoint -> not in I_M
        # (this is exactly the defeasibility pattern Simonelli identifies)
        assert stop_sign_implications["row-3"] not in frame

    def test_clause_i_containment_witness(
        self,
        stop_sign_bearers: dict[str, Bearer],
        stop_sign_endorsements: dict[Implication, Verdict],
    ) -> None:
        frame = DerivedFrame.from_endorsements(stop_sign_bearers, stop_sign_endorsements)
        # <{sa}, {sa, ra}> has Gamma cap Delta = {sa} != empty -> in I_M via (i)
        # even though no E_M verdict was recorded for it
        imp = Implication.of(["sa"], ["sa", "ra"])
        assert imp not in frame.queried_implications()
        assert frame.contains(imp)

    def test_excludes_empty_empty(
        self,
        stop_sign_bearers: dict[str, Bearer],
        stop_sign_endorsements: dict[Implication, Verdict],
    ) -> None:
        frame = DerivedFrame.from_endorsements(stop_sign_bearers, stop_sign_endorsements)
        # By stipulation: <emptyset, emptyset> not in I_M
        assert not frame.contains(Implication.of([], []))

    def test_unqueried_disjoint_implication_not_in_frame(
        self,
        stop_sign_bearers: dict[str, Bearer],
        stop_sign_endorsements: dict[Implication, Verdict],
    ) -> None:
        frame = DerivedFrame.from_endorsements(stop_sign_bearers, stop_sign_endorsements)
        # No clause (i), no recorded endorsement -> not in I_M
        unrelated = Implication.of(["n"], ["ra"])
        assert unrelated not in frame.queried_implications()
        assert not frame.contains(unrelated)

    def test_abstain_does_not_imply_membership(
        self,
        stop_sign_bearers: dict[str, Bearer],
    ) -> None:
        # Clause (ii) requires E_M = good specifically. Abstain != good.
        imp = Implication.of(["sa"], ["ra"])
        frame = DerivedFrame.from_endorsements(
            stop_sign_bearers, {imp: Verdict.ABSTAIN}
        )
        assert not frame.contains(imp)


# ---- Containment invariant ----------------------------------------------


class TestContainment:
    def test_holds_for_empty_frame(self, stop_sign_bearers: dict[str, Bearer]) -> None:
        frame = DerivedFrame.from_endorsements(stop_sign_bearers, {})
        assert frame.satisfies_containment()

    def test_holds_for_stop_sign(
        self,
        stop_sign_bearers: dict[str, Bearer],
        stop_sign_endorsements: dict[Implication, Verdict],
    ) -> None:
        frame = DerivedFrame.from_endorsements(stop_sign_bearers, stop_sign_endorsements)
        assert frame.satisfies_containment()
