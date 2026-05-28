"""Test-retest reliability analysis across two evaluations of the same benchmark.

Within-model analog of κ_F* (the inter-analyst peer baseline): how much
of the measured model-vs-analyst agreement is shared across replications
of the same evaluation, vs. how much is run-specific noise. A
substantively-unstable test-retest κ caps the construct-validity
verdict at ``partially_defensible`` (the same "ran but didn't pass"
audit-cap pattern applied for structural anomalies and m<2).

The methodology framing: an evaluation run once is not a measurement —
it's a draw from a distribution. Without a re-run there is no way to
tell whether the headline κ_C is signal or run-specific noise. R22
("test-retest reliability is reported and meets the methodology's
stability criterion") is required at scope >= ``domain_D_as_sampled``;
at ``items_in_benchmark`` scope the retest is informational, not
gating.

The implementation compares two :class:`~infereval.evaluation.Evaluation`
artifacts against the same benchmark. The framework can audit that the
two artifacts have the same ``benchmark_hash`` and the same
``endorsement_config`` (so test-retest variability isn't conflated with
parameter-change effects). It cannot audit that the two runs happened
on different occasions — the analyst's honesty in producing two
independent runs is the audit, with provider response IDs and
timestamps recorded as supporting evidence where available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from . import __version__

if TYPE_CHECKING:
    from .benchmark import Benchmark
    from .evaluation import Evaluation

log = logging.getLogger(__name__)


# Schema version for the RetestResult artifact JSON. Independent of
# framework version (per the same versioning discipline used for
# benchmark.json and evaluation.json). Bumps only on breaking changes
# to the artifact's content shape.
SCHEMA_VERSION: Literal["1.0"] = "1.0"


class RetestConfigMismatchError(ValueError):
    """Raised when two evaluations cannot be retest-compared because
    their configurations differ in ways that would conflate retest
    variability with parameter-change effects.

    Triggered by:
    - Different ``benchmark_hash`` (the runs were against different
      benchmarks, even if the ``benchmark_id`` matches).
    - Different ``endorsement_config`` (n_samples / tie_break / variant).
    - Different ``paraphrase_variant``.
    """


# ---- Data classes ---------------------------------------------------------


@dataclass(frozen=True)
class FlippedItem:
    """One item whose collapsed model verdict differs between two runs."""

    item_id: str
    verdict_a: str
    verdict_b: str
    #: Optional factor-level mapping for the item (when the benchmark
    #: declares factors). ``None`` when factors aren't declared or the
    #: benchmark isn't supplied.
    factor_levels: dict[str, str] | None = None


@dataclass(frozen=True)
class ItemDelta:
    """Per-item entropy/margin delta between two runs.

    Surfaces dispersion-level differences even when the collapsed
    verdict didn't flip. A high entropy delta on an item where the
    verdict was stable still indicates that the sampling was less
    reproducible than the verdict suggests.
    """

    item_id: str
    verdict_a: str
    verdict_b: str
    entropy_a: float
    entropy_b: float
    margin_a: float
    margin_b: float

    @property
    def entropy_delta(self) -> float:
        return abs(self.entropy_a - self.entropy_b)

    @property
    def margin_delta(self) -> float:
        return abs(self.margin_a - self.margin_b)


@dataclass(frozen=True)
class RetestResult:
    """Comparison of two evaluations as a test-retest reliability artifact.

    Mirrors the shape of :class:`infereval.sweep.SweepResult` so that
    the report-renderer integration in
    :mod:`infereval.report` can consume it via the same pattern as the
    other analytical artifacts (``structure``, ``sweep``, ``model``).
    """

    schema_version: Literal["1.0"]
    framework_version: str
    benchmark_id: str
    benchmark_hash: str | None
    run_a_id: str
    run_b_id: str
    n_items: int
    n_agreements: int
    n_disagreements: int
    test_retest_kappa: float | None
    flipped_items: tuple[FlippedItem, ...] = field(default_factory=tuple)
    item_deltas: tuple[ItemDelta, ...] = field(default_factory=tuple)

    @property
    def agreement_rate(self) -> float:
        """Fraction of items where the collapsed verdict matched across runs."""
        if self.n_items == 0:
            return 0.0
        return self.n_agreements / self.n_items

    @property
    def flip_rate(self) -> float:
        """Fraction of items whose collapsed verdict flipped across runs."""
        if self.n_items == 0:
            return 0.0
        return self.n_disagreements / self.n_items

    @property
    def stability_verdict(self) -> str:
        """Single-sentence assessment of test-retest reliability.

        Ladder mirrors :attr:`infereval.sweep.SweepResult.stability_verdict`:

        - ``kappa >= 0.8`` -> "stable; verdict-flip rate F%."
        - ``0.6 <= kappa < 0.8`` -> "moderately stable; F% of items flipped."
        - ``kappa < 0.6`` -> "substantively unstable; F% flipped — model
          output for this benchmark is not reliable enough for the
          headline κ_C to be interpreted as signal."

        When ``test_retest_kappa`` is ``None`` (degenerate p_e on the
        retest comparison column), reports an explicit "undefined"
        message rather than a verdict; consumers (notably
        :func:`infereval.report.compute_verdict`) should treat
        ``None`` as not-passing for audit-cap purposes.
        """
        k = self.test_retest_kappa
        flip_pct = self.flip_rate * 100
        if k is None:
            return (
                "test-retest κ is undefined on this comparison (degenerate "
                "agreement structure); reliability cannot be assessed from "
                "this run pair"
            )
        if k >= 0.8:
            return (
                f"test-retest reliability is stable (κ = {k:+.3f}); "
                f"verdict-flip rate {flip_pct:.1f}%."
            )
        if k >= 0.6:
            return (
                f"test-retest reliability is moderately stable (κ = {k:+.3f}); "
                f"{flip_pct:.1f}% of items flipped between runs."
            )
        return (
            f"test-retest reliability is substantively unstable "
            f"(κ = {k:+.3f}); {flip_pct:.1f}% of items flipped between "
            f"runs — model output for this benchmark is not reliable "
            f"enough for the headline κ_C to be interpreted as signal."
        )


# ---- Comparison logic -----------------------------------------------------


def _check_compatibility(
    eta_a: Evaluation, eta_b: Evaluation
) -> None:
    """Raise :class:`RetestConfigMismatchError` if the two evals can't be compared."""
    if eta_a.benchmark_id != eta_b.benchmark_id:
        raise RetestConfigMismatchError(
            f"benchmark_id mismatch: run A used {eta_a.benchmark_id!r}, "
            f"run B used {eta_b.benchmark_id!r}; retest comparison requires "
            f"the same benchmark"
        )
    if (
        eta_a.benchmark_hash is not None
        and eta_b.benchmark_hash is not None
        and eta_a.benchmark_hash != eta_b.benchmark_hash
    ):
        raise RetestConfigMismatchError(
            f"benchmark_hash mismatch: run A = {eta_a.benchmark_hash[:12]}…, "
            f"run B = {eta_b.benchmark_hash[:12]}…; the benchmark was edited "
            f"between runs (or one of the artifacts was tampered with)"
        )
    if eta_a.endorsement_config != eta_b.endorsement_config:
        raise RetestConfigMismatchError(
            f"endorsement_config mismatch: run A = "
            f"{eta_a.endorsement_config}, run B = {eta_b.endorsement_config}; "
            f"retest variability would be conflated with parameter-change "
            f"effects (use `infereval sweep` for parameter sensitivity instead)"
        )
    if eta_a.paraphrase_variant != eta_b.paraphrase_variant:
        raise RetestConfigMismatchError(
            f"paraphrase_variant mismatch: run A = "
            f"{eta_a.paraphrase_variant}, run B = {eta_b.paraphrase_variant}; "
            f"retest variability would be conflated with paraphrase-axis "
            f"effects (use `infereval evaluate --paraphrase-cycle` for "
            f"paraphrase-axis runs and `infereval retest` within a single "
            f"variant)"
        )


def _retest_cohens_kappa(
    verdicts_a: list[str], verdicts_b: list[str]
) -> float | None:
    """Cohen's κ over two columns of collapsed verdicts (post tie-break).

    Restricted to items where both verdicts are substantive (``good`` /
    ``bad``). Returns ``None`` when the substantive subset is empty or
    ``p_e == 1``. Same conventions as :func:`infereval.metrics.cohens_kappa`
    but operates on plain string columns rather than over an
    :class:`Evaluation`.
    """
    from .types import Verdict

    substantive = {Verdict.GOOD.value, Verdict.BAD.value}
    pairs = [
        (a, b)
        for a, b in zip(verdicts_a, verdicts_b, strict=True)
        if a in substantive and b in substantive
    ]
    if not pairs:
        return None
    n = len(pairs)
    p_o = sum(1 for a, b in pairs if a == b) / n
    cats = (Verdict.GOOD.value, Verdict.BAD.value)
    p_a = {c: sum(1 for a, _ in pairs if a == c) / n for c in cats}
    p_b = {c: sum(1 for _, b in pairs if b == c) / n for c in cats}
    p_e = sum(p_a[c] * p_b[c] for c in cats)
    if abs(1.0 - p_e) < 1e-12:
        return None
    return (p_o - p_e) / (1.0 - p_e)


def compute_retest(
    eta_a: Evaluation,
    eta_b: Evaluation,
    benchmark: Benchmark | None = None,
) -> RetestResult:
    """Compare two evaluations and return a :class:`RetestResult`.

    Parameters
    ----------
    eta_a, eta_b
        The two evaluations. Must share the same benchmark hash, the
        same endorsement configuration, and the same paraphrase
        variant; otherwise :class:`RetestConfigMismatchError` is
        raised.
    benchmark
        Optional :class:`infereval.benchmark.Benchmark`. When supplied,
        each :class:`FlippedItem` is annotated with the item's
        ``factor_levels`` so downstream analysis can correlate flips
        with design factors.

    Returns
    -------
    RetestResult
        Includes the per-item flips, per-item dispersion deltas, the
        test-retest κ, and the stability verdict.
    """
    from .metrics import verdict_distribution

    _check_compatibility(eta_a, eta_b)

    items_a = {it.id: it for it in eta_a.items}
    items_b = {it.id: it for it in eta_b.items}
    common_ids = sorted(items_a.keys() & items_b.keys())
    only_a = sorted(items_a.keys() - items_b.keys())
    only_b = sorted(items_b.keys() - items_a.keys())
    if only_a or only_b:
        log.warning(
            "compute_retest: item-id mismatch — only-in-A: %s; only-in-B: %s; "
            "the retest comparison runs over the intersection only (n=%d)",
            only_a[:5],
            only_b[:5],
            len(common_ids),
        )

    # Build factor-level lookup if a benchmark is supplied.
    factor_levels_by_id: dict[str, dict[str, str]] = {}
    if benchmark is not None:
        for bi in benchmark.items:
            fl = getattr(bi, "factor_levels", None)
            if fl:
                factor_levels_by_id[bi.id] = dict(fl)

    verdicts_a: list[str] = []
    verdicts_b: list[str] = []
    flipped: list[FlippedItem] = []
    deltas: list[ItemDelta] = []
    n_agree = 0
    n_disagree = 0
    for item_id in common_ids:
        ia = items_a[item_id]
        ib = items_b[item_id]
        va = ia.model_verdict.value
        vb = ib.model_verdict.value
        verdicts_a.append(va)
        verdicts_b.append(vb)
        if va == vb:
            n_agree += 1
        else:
            n_disagree += 1
            flipped.append(
                FlippedItem(
                    item_id=item_id,
                    verdict_a=va,
                    verdict_b=vb,
                    factor_levels=factor_levels_by_id.get(item_id),
                )
            )
        da = verdict_distribution(ia)
        db = verdict_distribution(ib)
        deltas.append(
            ItemDelta(
                item_id=item_id,
                verdict_a=va,
                verdict_b=vb,
                entropy_a=da.entropy,
                entropy_b=db.entropy,
                margin_a=da.margin,
                margin_b=db.margin,
            )
        )

    kappa = _retest_cohens_kappa(verdicts_a, verdicts_b)

    return RetestResult(
        schema_version=SCHEMA_VERSION,
        framework_version=__version__,
        benchmark_id=eta_a.benchmark_id,
        benchmark_hash=eta_a.benchmark_hash,
        run_a_id=eta_a.id,
        run_b_id=eta_b.id,
        n_items=len(common_ids),
        n_agreements=n_agree,
        n_disagreements=n_disagree,
        test_retest_kappa=kappa,
        flipped_items=tuple(flipped),
        item_deltas=tuple(deltas),
    )


def retest_result_to_dict(result: RetestResult) -> dict[str, object]:
    """Render :class:`RetestResult` as a JSON-friendly dict.

    Stable shape — consumed by the report renderer and persisted as
    ``retest-result.json`` by the CLI.
    """
    return {
        "schema_version": result.schema_version,
        "framework_version": result.framework_version,
        "benchmark_id": result.benchmark_id,
        "benchmark_hash": result.benchmark_hash,
        "run_a_id": result.run_a_id,
        "run_b_id": result.run_b_id,
        "n_items": result.n_items,
        "n_agreements": result.n_agreements,
        "n_disagreements": result.n_disagreements,
        "agreement_rate": result.agreement_rate,
        "flip_rate": result.flip_rate,
        "test_retest_kappa": result.test_retest_kappa,
        "stability_verdict": result.stability_verdict,
        "flipped_items": [
            {
                "item_id": fi.item_id,
                "verdict_a": fi.verdict_a,
                "verdict_b": fi.verdict_b,
                "factor_levels": fi.factor_levels,
            }
            for fi in result.flipped_items
        ],
        "item_deltas": [
            {
                "item_id": d.item_id,
                "verdict_a": d.verdict_a,
                "verdict_b": d.verdict_b,
                "entropy_a": d.entropy_a,
                "entropy_b": d.entropy_b,
                "entropy_delta": d.entropy_delta,
                "margin_a": d.margin_a,
                "margin_b": d.margin_b,
                "margin_delta": d.margin_delta,
            }
            for d in result.item_deltas
        ],
    }


__all__ = [
    "SCHEMA_VERSION",
    "FlippedItem",
    "ItemDelta",
    "RetestConfigMismatchError",
    "RetestResult",
    "compute_retest",
    "retest_result_to_dict",
]
