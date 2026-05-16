"""Core data types for the infereval framework.

Tracks the notation in revised.tex (Allen 2026):

- :class:`Verdict` -- the codomain of :math:`E_M`: ``good`` / ``bad`` / ``abstain``.
- :class:`Bearer` -- an element of the bearer set :math:`B`. Carries its id, the
  canonical natural-language expression :math:`\\delta(\\varphi)`, and an optional
  paraphrase family (for the second axis of variation discussed in the paper's
  Discussion section, Remark on "Two dimensions of variation").
- :class:`Implication` -- a candidate implication :math:`\\langle \\Gamma, \\Delta \\rangle`.
  Premises and conclusions are stored as ``frozenset[str]`` of bearer ids so the
  instance is hashable and usable as a dict key (see
  :class:`infereval.frame.DerivedFrame`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    """Endorsement verdict :math:`E_M(\\langle \\Gamma, \\Delta \\rangle)`.

    String-valued so JSON serialization yields ``"good"`` / ``"bad"`` / ``"abstain"``
    directly. The ``(str, Enum)`` pattern is used in place of
    :class:`enum.StrEnum` for Python 3.10 compatibility.
    """

    GOOD = "good"
    BAD = "bad"
    ABSTAIN = "abstain"

    def __str__(self) -> str:  # so f-strings produce "good" not "Verdict.GOOD"
        return self.value


@dataclass(frozen=True, slots=True)
class Bearer:
    """A propositional content-bearer :math:`\\varphi \\in B`.

    Parameters
    ----------
    id
        Short stable identifier, e.g. ``"sa"`` for "a is a stop sign".
    expression
        Canonical natural-language statement :math:`\\delta(\\varphi)`.
        May contain TeX-math delimiters (e.g. ``"$a$ is a stop sign"``); these
        are stripped at prompt-construction time, not here.
    paraphrases
        Optional family of meaning-preserving variants of :math:`\\delta(\\varphi)`.
        Empty by default. Supports the paraphrase axis of variation discussed in
        the paper's Discussion.
    """

    id: str
    expression: str
    paraphrases: tuple[str, ...] = ()

    def all_expressions(self) -> tuple[str, ...]:
        """Return the canonical expression followed by any paraphrases."""
        return (self.expression, *self.paraphrases)


@dataclass(frozen=True, slots=True)
class Implication:
    """A candidate implication :math:`\\langle \\Gamma, \\Delta \\rangle`.

    Premises and conclusions are ``frozenset`` of bearer ids (the ``id`` field of
    :class:`Bearer`). The optional ``id`` field is a benchmark-level reference
    label; it is excluded from equality and hashing so that two implications with
    the same premise/conclusion sets compare equal regardless of label.
    """

    premises: frozenset[str]
    conclusions: frozenset[str]
    id: str | None = field(default=None, compare=False)

    @classmethod
    def of(
        cls,
        premises: Iterable[str],
        conclusions: Iterable[str],
        *,
        id: str | None = None,
    ) -> Implication:
        """Convenience constructor accepting any iterables of bearer ids."""
        return cls(frozenset(premises), frozenset(conclusions), id=id)

    @property
    def is_empty_empty(self) -> bool:
        """Whether this is the :math:`\\langle \\emptyset, \\emptyset \\rangle` implication.

        Excluded from :math:`I_M` by stipulation (Definition 3, last sentence).
        """
        return not self.premises and not self.conclusions

    def intersects(self) -> bool:
        """Whether :math:`\\Gamma \\cap \\Delta \\neq \\emptyset` (Definition 3, clause (i))."""
        return bool(self.premises & self.conclusions)
