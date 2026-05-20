"""Metrics for an evaluation :math:`\\eta`.

Implements revised.tex Section 4 ("Evaluation methodology"):

- Coverage :math:`\\mathrm{cov}(\\eta)` and per-analyst coverage
  :math:`\\mathrm{cov}_j(\\eta)`.
- Substantive index :math:`S(\\eta, r)` against a reference verdict
  function :math:`r`.
- Analyst consensus :math:`c_i`.
- Cohen's kappa :math:`\\kappa_C(\\eta, r)` against any reference.
- Fleiss' kappa :math:`\\kappa_F(\\eta)` with :math:`M` as the
  :math:`(m+1)`-th annotator.
- Inter-analyst baseline :math:`\\kappa_F^*(\\beta)` over analyst verdicts
  alone (the comparison point of Remark 5).

Edge cases the paper flags are returned as :data:`None` (with a logged
warning) rather than raised: :math:`\\kappa_F^*` needs :math:`m \\geq 2`
and non-unanimity; :math:`\\kappa_C` is undefined when
:math:`p_e = 1`; both kappa variants are undefined when the relevant
substantive subset is empty.

The high-level :class:`MetricsReport` aggregator bundles all of the above
into a single object suitable for JSON-printing, with ``by_tag`` and
``by_rsr_target`` filters for the decompositions Section 4 calls out.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .types import Verdict

if TYPE_CHECKING:
    from .benchmark import Benchmark
    from .evaluation import Evaluation

log = logging.getLogger(__name__)

#: Type alias: a reference verdict function ``r(i) -> Verdict``.
ReferenceFn = Callable[[int], Verdict]

#: Verdicts that count as "substantive" for the kappa definitions.
SUBSTANTIVE: frozenset[Verdict] = frozenset({Verdict.GOOD, Verdict.BAD})


# ---- Coverage --------------------------------------------------------------


def coverage(eta: Evaluation) -> float:
    """:math:`\\mathrm{cov}(\\eta) = |\\{i : E_M(I_i) \\neq \\text{abstain}\\}| / n`.

    Returns ``0.0`` for an empty evaluation rather than raising.
    """
    if eta.n == 0:
        return 0.0
    substantive = sum(1 for it in eta.items if it.model_verdict != Verdict.ABSTAIN)
    return substantive / eta.n


def coverage_analyst(eta: Evaluation, analyst_index: int) -> float:
    """:math:`\\mathrm{cov}_j(\\eta) = |\\{i : v_{i,j} \\neq \\text{abstain}\\}| / n`.

    ``analyst_index`` is 0-based and must be ``< m``.
    """
    if eta.n == 0:
        return 0.0
    substantive = sum(
        1
        for it in eta.items
        if it.analyst_verdicts[analyst_index] != Verdict.ABSTAIN
    )
    return substantive / eta.n


def coverage_per_analyst(eta: Evaluation) -> list[float]:
    """Per-analyst coverage as a list indexed by analyst position.

    Returns an empty list if ``eta`` has no items.
    """
    if eta.n == 0:
        return []
    m = len(eta.items[0].analyst_verdicts)
    return [coverage_analyst(eta, j) for j in range(m)]


# ---- Consensus -------------------------------------------------------------


def consensus_verdict(verdicts: Sequence[Verdict]) -> Verdict:
    """Return the analyst consensus :math:`c_i` for one item's verdicts.

    From revised.tex Definition 7: ``good`` if strict majority of analysts
    say ``good`` (vs. ``bad``); ``bad`` if strict majority say ``bad``;
    otherwise ``abstain``. Abstain votes do not count toward the majority
    of either substantive class but contribute to a tie.
    """
    good = sum(1 for v in verdicts if v == Verdict.GOOD)
    bad = sum(1 for v in verdicts if v == Verdict.BAD)
    if good > bad:
        return Verdict.GOOD
    if bad > good:
        return Verdict.BAD
    return Verdict.ABSTAIN


def consensus_reference(eta: Evaluation) -> ReferenceFn:
    """Return :math:`r(i) = c_i` as a :data:`ReferenceFn`."""
    per_item = [consensus_verdict(it.analyst_verdicts) for it in eta.items]

    def _ref(i: int) -> Verdict:
        return per_item[i]

    return _ref


def analyst_reference(eta: Evaluation, analyst_index: int) -> ReferenceFn:
    """Return :math:`r(i) = v_{i, \\text{analyst\\_index}}` as a :data:`ReferenceFn`."""
    per_item = [it.analyst_verdicts[analyst_index] for it in eta.items]

    def _ref(i: int) -> Verdict:
        return per_item[i]

    return _ref


# ---- Substantive index ----------------------------------------------------


def substantive_index(eta: Evaluation, reference: ReferenceFn) -> set[int]:
    """:math:`S(\\eta, r) = \\{i : E_M(I_i) \\in \\{\\text{good},\\text{bad}\\} \\wedge r(i) \\in \\{\\text{good},\\text{bad}\\}\\}`."""
    return {
        i
        for i, it in enumerate(eta.items)
        if it.model_verdict in SUBSTANTIVE and reference(i) in SUBSTANTIVE
    }


# ---- Cohen's kappa --------------------------------------------------------


def cohens_kappa(eta: Evaluation, reference: ReferenceFn) -> float | None:
    """:math:`\\kappa_C(\\eta, r) = (p_o - p_e) / (1 - p_e)`.

    Returns :data:`None` when :math:`S(\\eta, r)` is empty or
    :math:`p_e = 1` (degenerate distribution). Logs a warning in both
    cases so the user sees why the value is undefined.
    """
    S = sorted(substantive_index(eta, reference))
    if not S:
        log.warning(
            "kappa_C undefined: substantive subset S(eta, r) is empty"
        )
        return None

    n_S = len(S)
    p_o = sum(1 for i in S if eta.items[i].model_verdict == reference(i)) / n_S

    p_M: dict[Verdict, float] = {}
    p_r: dict[Verdict, float] = {}
    for c in (Verdict.GOOD, Verdict.BAD):
        p_M[c] = sum(1 for i in S if eta.items[i].model_verdict == c) / n_S
        p_r[c] = sum(1 for i in S if reference(i) == c) / n_S

    p_e = sum(p_M[c] * p_r[c] for c in (Verdict.GOOD, Verdict.BAD))

    if abs(1.0 - p_e) < 1e-12:
        log.warning(
            "kappa_C undefined: chance-expected agreement p_e = 1 "
            "(M and reference both degenerate on a single class over S)"
        )
        return None

    return (p_o - p_e) / (1.0 - p_e)


# ---- Fleiss' kappa --------------------------------------------------------


def _fleiss_over_tuples(verdict_tuples: Sequence[Sequence[Verdict]]) -> float | None:
    """Fleiss' kappa over a list of equal-length annotator tuples.

    Items with any non-substantive verdict are dropped (matching the
    ``S_F`` / ``S`` filtering in revised.tex Definition 9 and Remark 5).
    """
    if not verdict_tuples:
        log.warning("Fleiss kappa undefined: no items")
        return None

    n_annotators = len(verdict_tuples[0])
    if n_annotators < 2:
        log.warning("Fleiss kappa undefined: fewer than 2 annotators")
        return None
    if any(len(vs) != n_annotators for vs in verdict_tuples):
        raise ValueError("All annotator tuples must have the same length")

    # Filter to fully-substantive items
    S_F = [
        vs
        for vs in verdict_tuples
        if all(v in SUBSTANTIVE for v in vs)
    ]
    n_F = len(S_F)
    if n_F == 0:
        log.warning("Fleiss kappa undefined: no items with all-substantive annotations")
        return None

    cat_totals: dict[Verdict, int] = {Verdict.GOOD: 0, Verdict.BAD: 0}
    per_item_P: list[float] = []
    pair_denom = n_annotators * (n_annotators - 1)

    for vs in S_F:
        n_ic = {
            Verdict.GOOD: sum(1 for v in vs if v == Verdict.GOOD),
            Verdict.BAD: sum(1 for v in vs if v == Verdict.BAD),
        }
        for c, count in n_ic.items():
            cat_totals[c] += count
        P_i = sum(n * (n - 1) for n in n_ic.values()) / pair_denom
        per_item_P.append(P_i)

    P_bar = sum(per_item_P) / n_F

    total_annotations = n_F * n_annotators
    p_c = {c: cat_totals[c] / total_annotations for c in (Verdict.GOOD, Verdict.BAD)}
    P_bar_e = sum(p * p for p in p_c.values())

    if abs(1.0 - P_bar_e) < 1e-12:
        log.warning(
            "Fleiss kappa undefined: chance-expected agreement P_bar_e = 1 "
            "(all annotations in one class over S_F)"
        )
        return None

    return (P_bar - P_bar_e) / (1.0 - P_bar_e)


def fleiss_kappa(eta: Evaluation) -> float | None:
    """:math:`\\kappa_F(\\eta)` with :math:`M` as the :math:`(m+1)`-th annotator.

    The annotators on each item are the analyst verdicts followed by
    ``model_verdict``. Items where any annotator (analyst or model) is
    non-substantive are excluded from :math:`S_F` per revised.tex
    Definition 9.
    """
    tuples = [
        [*item.analyst_verdicts, item.model_verdict] for item in eta.items
    ]
    return _fleiss_over_tuples(tuples)


def inter_analyst_fleiss(source: Evaluation | Benchmark) -> float | None:
    """:math:`\\kappa_F^*(\\beta)`: Fleiss' kappa over analyst verdicts alone.

    Accepts either an :class:`~infereval.evaluation.Evaluation` or a
    :class:`~infereval.benchmark.Benchmark`. Returns :data:`None` (with
    a logged warning) when :math:`m < 2` or when the analysts are
    unanimous on every item -- the two conditions Remark 5 calls out as
    making the baseline unavailable.

    For panelled benchmarks (Issue #36, Phase 1.4), this returns the
    κ_F* of the *primary* panel only — see
    :func:`inter_analyst_fleiss_per_panel` for per-panel breakdown and
    :func:`cross_panel_kappa` for the cross-panel agreement metric.
    """
    # Late import to avoid the metrics <-> benchmark cycle.
    from .benchmark import Benchmark as _Benchmark

    if isinstance(source, _Benchmark) and source.panel_names():
        primary = source.resolved_primary_panel()
        if primary is None:
            return None
        indices = source.analyst_indices_in_panel(primary)
        tuples = [[it.analyst_verdicts[j] for j in indices] for it in source.items]
        return _fleiss_over_tuples(tuples)
    items = source.items
    tuples = [list(it.analyst_verdicts) for it in items]
    return _fleiss_over_tuples(tuples)


def inter_analyst_fleiss_per_panel(
    benchmark: Benchmark,
) -> dict[str, float | None]:
    """:math:`\\kappa_F^*` computed per analyst panel.

    Returns a mapping ``panel_name -> κ_F*`` for every panel declared on
    the benchmark. A panel value is ``None`` when the panel has fewer
    than 2 analysts or when the analysts are unanimous on every item
    (per the same conditions :func:`inter_analyst_fleiss` honours).

    Empty dict if the benchmark is unpanelled. Phase 1.4 of the
    construct-validity infrastructure (R4).
    """
    out: dict[str, float | None] = {}
    for name in benchmark.panel_names():
        indices = benchmark.analyst_indices_in_panel(name)
        tuples = [
            [it.analyst_verdicts[j] for j in indices] for it in benchmark.items
        ]
        out[name] = _fleiss_over_tuples(tuples)
    return out


def _panel_consensus_verdict(
    item_verdicts: Sequence[Verdict],
    indices: Sequence[int],
) -> Verdict:
    """Majority verdict among the indexed analysts; abstain on tie.

    Used as the per-item consensus for cross-panel agreement
    calculations. Matches the conservative tie-break the framework uses
    elsewhere (per CLAUDE.md locked methodology defaults).
    """
    counts = Counter(item_verdicts[j] for j in indices)
    if not counts:
        return Verdict.ABSTAIN
    top = counts.most_common(1)[0][1]
    winners = [v for v, c in counts.items() if c == top]
    if len(winners) > 1:
        return Verdict.ABSTAIN
    return winners[0]


def cross_panel_kappa(
    benchmark: Benchmark,
    *,
    primary: str | None = None,
    check: str | None = None,
) -> float | None:
    """Cohen's :math:`\\kappa_C` between two panels' per-item consensus verdicts.

    Computes a per-panel consensus verdict for each item (majority among
    panel members, abstain on tie) and then runs Cohen's kappa between
    the two columns, restricted to items where both panels yield a
    substantive verdict.

    Parameters
    ----------
    benchmark
        Panelled benchmark.
    primary
        Name of the primary panel. Defaults to
        ``benchmark.resolved_primary_panel()``.
    check
        Name of the panel to compare against. When ``None`` and exactly
        two panels are declared, picks the non-primary one
        automatically.

    Returns
    -------
    float | None
        Cohen's kappa over the substantive-on-both items, or ``None``
        when fewer than two non-trivial agreement counts are available,
        or when either named panel doesn't exist.

    Phase 1.4 of the construct-validity infrastructure (R4 — guards
    against shared-error agreement within the primary panel by
    surfacing the independent panel's view).
    """
    names = benchmark.panel_names()
    if primary is None:
        primary = benchmark.resolved_primary_panel()
    if primary is None or primary not in names:
        log.warning(
            "cross_panel_kappa: primary panel %r not declared on benchmark %r",
            primary,
            benchmark.id,
        )
        return None
    if check is None:
        others = [n for n in names if n != primary]
        if len(others) != 1:
            log.warning(
                "cross_panel_kappa: 'check' panel must be supplied when the "
                "benchmark declares != 2 panels (declared: %s)",
                names,
            )
            return None
        check = others[0]
    if check not in names:
        log.warning(
            "cross_panel_kappa: check panel %r not declared on benchmark %r",
            check,
            benchmark.id,
        )
        return None

    primary_idx = benchmark.analyst_indices_in_panel(primary)
    check_idx = benchmark.analyst_indices_in_panel(check)

    primary_col = [
        _panel_consensus_verdict(it.analyst_verdicts, primary_idx)
        for it in benchmark.items
    ]
    check_col = [
        _panel_consensus_verdict(it.analyst_verdicts, check_idx)
        for it in benchmark.items
    ]

    # Restrict to items where both panels reached a substantive consensus.
    pairs = [
        (p, c)
        for p, c in zip(primary_col, check_col, strict=True)
        if p != Verdict.ABSTAIN and c != Verdict.ABSTAIN
    ]
    if not pairs:
        log.warning(
            "cross_panel_kappa: empty substantive intersection between panels "
            "%r and %r on benchmark %r",
            primary,
            check,
            benchmark.id,
        )
        return None

    cats = (Verdict.GOOD, Verdict.BAD)
    n = len(pairs)
    p_obs = sum(1 for p, c in pairs if p == c) / n
    pa = {v: sum(1 for p, _ in pairs if p == v) / n for v in cats}
    pc = {v: sum(1 for _, c in pairs if c == v) / n for v in cats}
    p_exp = sum(pa[v] * pc[v] for v in cats)
    if abs(1 - p_exp) < 1e-12:
        log.warning(
            "cross_panel_kappa: chance-expected agreement = 1 (one panel is "
            "fully degenerate to a single class); kappa is undefined"
        )
        return None
    return (p_obs - p_exp) / (1 - p_exp)


# ---- High-level aggregator -----------------------------------------------


@dataclass
class MetricsReport:
    """Bundle of metrics over an :class:`Evaluation`, with decomposition filters.

    Parameters
    ----------
    eta
        The evaluation to report on.
    benchmark
        Optional benchmark. Required for :meth:`by_rsr_target` and
        :meth:`coverage_per_analyst_named`; other methods work without it.
    """

    eta: Evaluation
    benchmark: Benchmark | None = None

    # ---- Coverage ----

    @property
    def n(self) -> int:
        """Number of evaluation items."""
        return self.eta.n

    @property
    def coverage(self) -> float:
        return coverage(self.eta)

    @property
    def coverage_per_analyst(self) -> list[float]:
        return coverage_per_analyst(self.eta)

    def coverage_per_analyst_named(self) -> dict[str, float]:
        """Per-analyst coverage keyed by analyst id (requires :attr:`benchmark`)."""
        if self.benchmark is None:
            raise ValueError(
                "coverage_per_analyst_named requires a benchmark to resolve analyst ids"
            )
        return {
            a.id: coverage_analyst(self.eta, j)
            for j, a in enumerate(self.benchmark.analysts)
        }

    # ---- Kappa ----

    def cohens_kappa(self, reference: ReferenceFn | None = None) -> float | None:
        """:math:`\\kappa_C(\\eta, r)`. Default reference is the analyst consensus :math:`c_i`."""
        ref = reference if reference is not None else consensus_reference(self.eta)
        return cohens_kappa(self.eta, ref)

    def cohens_kappa_analyst(self, analyst_index: int) -> float | None:
        """:math:`\\kappa_C(\\eta, v_{:,j})`: M vs. one specific analyst."""
        return cohens_kappa(self.eta, analyst_reference(self.eta, analyst_index))

    @property
    def fleiss_kappa(self) -> float | None:
        return fleiss_kappa(self.eta)

    @property
    def inter_analyst_fleiss(self) -> float | None:
        return inter_analyst_fleiss(self.eta)

    # ---- Filters ----

    def by_tag(self, tag: str) -> MetricsReport:
        """Return a report restricted to items carrying ``tag``."""
        filtered = self.eta.model_copy(
            update={"items": [it for it in self.eta.items if tag in it.tags]}
        )
        return MetricsReport(eta=filtered, benchmark=self.benchmark)

    def by_rsr_target(self, X: frozenset[str], A: frozenset[str]) -> MetricsReport:
        """Return a report restricted to items whose ``rsr_target`` matches ``(X, A)``.

        ``rsr_target`` lives on benchmark items, not evaluation items, so
        :attr:`benchmark` is required.
        """
        if self.benchmark is None:
            raise ValueError("by_rsr_target requires a benchmark to read rsr_target fields")
        keep_ids = {
            bi.id
            for bi in self.benchmark.items
            if bi.rsr_target is not None
            and frozenset(bi.rsr_target.X) == X
            and frozenset(bi.rsr_target.A) == A
        }
        filtered = self.eta.model_copy(
            update={"items": [it for it in self.eta.items if it.id in keep_ids]}
        )
        return MetricsReport(eta=filtered, benchmark=self.benchmark)

    # ---- Reporting ----

    def to_dict(self) -> dict[str, Any]:
        """Render as a JSON-friendly dict (None where a kappa is undefined)."""
        out: dict[str, Any] = {
            "n": self.n,
            "coverage": self.coverage,
            "coverage_per_analyst": self.coverage_per_analyst,
            "cohens_kappa_consensus": self.cohens_kappa(),
            "fleiss_kappa": self.fleiss_kappa,
            "inter_analyst_fleiss": self.inter_analyst_fleiss,
        }
        if self.benchmark is not None:
            out["coverage_per_analyst_named"] = self.coverage_per_analyst_named()
        return out


__all__ = [
    "SUBSTANTIVE",
    "MetricsReport",
    "ReferenceFn",
    "analyst_reference",
    "cohens_kappa",
    "consensus_reference",
    "consensus_verdict",
    "coverage",
    "coverage_analyst",
    "coverage_per_analyst",
    "fleiss_kappa",
    "inter_analyst_fleiss",
    "substantive_index",
]
