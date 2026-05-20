"""Sensitivity-analysis sweeps over evaluation parameters.

Phase 2.3 of the construct-validity infrastructure (per *Closing the
Construct-Validity Gap in infereval*). Closes Phase 2 (analytical
extensions). Addresses **R11** (sensitivity analysis on free
parameters).

The module orchestrates a sequence of :func:`infereval.evaluation.evaluate`
calls under varied methodological parameters (``n_samples``,
``tie_break``, ``paraphrase_variant``, ``temperature``) and bundles the
per-value metrics into a summary. Each per-value run reuses the existing
evaluation infrastructure unchanged — the sweep is pure orchestration.

The framework's locked methodology defaults (per CLAUDE.md) are
appropriate baselines; the sweep is for showing the robustness of
agreement *to those choices*, not for re-tuning them. A stable sweep
(κ_C range < 0.05) reports as such; an unstable sweep escalates the
language so the reader is told to consider tighter parameter choices
or a wider analyst panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .evaluation import EndorsementConfig, ProviderParams, evaluate
from .metrics import (
    cohens_kappa,
    consensus_reference,
    coverage,
    fleiss_kappa,
)

if TYPE_CHECKING:
    from .benchmark import Benchmark
    from .providers.base import Provider


# Supported sweep parameters and how their string values coerce.
_SUPPORTED_PARAMS: dict[str, type] = {
    "n_samples": int,
    "tie_break": str,
    "paraphrase_variant": int,
    "temperature": float,
}

_VALID_TIE_BREAKS = {"abstain", "good", "bad", "first"}


class SweepError(ValueError):
    """Raised when the sweep configuration is invalid."""


@dataclass(frozen=True)
class SweepRow:
    """One row of the sweep summary: parameters + metrics for one value."""

    value: object
    """The swept parameter's value for this row, type-coerced per the parameter."""
    coverage: float
    kappa_c: float | None
    kappa_f: float | None
    n_agreement: int
    """Count of items where ``model_verdict == consensus_reference``."""
    n_total: int
    eta_path: Path
    """On-disk location of the per-value evaluation JSON."""


@dataclass(frozen=True)
class SweepResult:
    """Bundle of per-value rows + an overall stability assessment."""

    parameter: str
    """Name of the swept parameter."""
    rows: tuple[SweepRow, ...]

    @property
    def kappa_c_range(self) -> float | None:
        """Max-minus-min of κ_C across rows; ``None`` if any κ_C is None."""
        ks = [r.kappa_c for r in self.rows if r.kappa_c is not None]
        if len(ks) < 2:
            return None
        return max(ks) - min(ks)

    @property
    def stability_verdict(self) -> str:
        """Human-readable single-sentence assessment of κ_C variation."""
        r = self.kappa_c_range
        if r is None:
            return "Insufficient data to assess stability (fewer than 2 defined κ_C values)."
        if r < 0.05:
            return (
                f"κ_C range = {r:.3f}; agreement is stable across the sweep range."
            )
        if r < 0.10:
            return (
                f"κ_C range = {r:.3f}; agreement is moderately sensitive to "
                f"the swept parameter."
            )
        return (
            f"κ_C range = {r:.3f}; agreement varies substantively across "
            f"the sweep range — consider tighter parameter choices or a "
            f"wider analyst panel."
        )


def coerce_values(parameter: str, raw_values: list[str]) -> list[object]:
    """Type-coerce raw string values for the swept parameter.

    Raises :class:`SweepError` on unknown parameter or unparseable values.
    """
    if parameter not in _SUPPORTED_PARAMS:
        raise SweepError(
            f"--vary {parameter!r}: supported parameters are "
            f"{sorted(_SUPPORTED_PARAMS)}"
        )
    target = _SUPPORTED_PARAMS[parameter]
    out: list[object] = []
    for raw in raw_values:
        v = raw.strip()
        if target is int:
            try:
                out.append(int(v))
            except ValueError as exc:
                raise SweepError(
                    f"--values: {v!r} is not a valid int for parameter {parameter!r}"
                ) from exc
        elif target is float:
            try:
                out.append(float(v))
            except ValueError as exc:
                raise SweepError(
                    f"--values: {v!r} is not a valid float for parameter {parameter!r}"
                ) from exc
        else:
            if parameter == "tie_break" and v not in _VALID_TIE_BREAKS:
                raise SweepError(
                    f"--values: {v!r} is not a valid tie_break choice; "
                    f"must be one of {sorted(_VALID_TIE_BREAKS)}"
                )
            out.append(v)
    return out


def _apply_value(
    parameter: str,
    value: object,
    config: EndorsementConfig,
    params: ProviderParams,
) -> tuple[EndorsementConfig, ProviderParams, int]:
    """Return (config, params, variant) with ``parameter`` set to ``value``.

    ``variant`` is the paraphrase variant; it's returned separately because
    it's not part of EndorsementConfig or ProviderParams — it's a top-level
    argument to :func:`evaluate`. ``value`` has already been type-coerced
    by :func:`coerce_values`, so the casts below are correct at runtime.
    """
    variant = 0
    if parameter == "n_samples":
        assert isinstance(value, int)
        config = config.model_copy(update={"n_samples": value})
    elif parameter == "tie_break":
        assert isinstance(value, str)
        config = config.model_copy(update={"tie_break": value})
    elif parameter == "paraphrase_variant":
        assert isinstance(value, int)
        variant = value
    elif parameter == "temperature":
        assert isinstance(value, (int, float))
        params = params.model_copy(update={"temperature": float(value)})
    return config, params, variant


def run_sweep(
    benchmark: Benchmark,
    provider: Provider,
    *,
    parameter: str,
    values: list[object],
    out_dir: Path,
    config: EndorsementConfig | None = None,
    params: ProviderParams | None = None,
    run_id_prefix: str | None = None,
) -> SweepResult:
    """Run :func:`evaluate` once per value and bundle the metrics.

    Per-value outputs land in ``out_dir`` with deterministic names so a
    re-run replaces them in place.
    """
    if parameter not in _SUPPORTED_PARAMS:
        raise SweepError(f"unsupported sweep parameter: {parameter!r}")
    if not values:
        raise SweepError("--values must contain at least one value")

    out_dir.mkdir(parents=True, exist_ok=True)
    base_config = config or EndorsementConfig()
    base_params = params or ProviderParams()

    rows: list[SweepRow] = []
    for value in values:
        cfg, par, variant = _apply_value(parameter, value, base_config, base_params)

        # Render value into a filename-safe form.
        value_str = str(value).replace("/", "-").replace(" ", "_")
        eta_path = out_dir / f"sweep-{parameter}={value_str}-eta.json"
        log_path = out_dir / f"sweep-{parameter}={value_str}-run.jsonl"

        rid = (
            f"{run_id_prefix}-{parameter}={value_str}"
            if run_id_prefix
            else f"sweep-{parameter}={value_str}"
        )

        eta = evaluate(
            benchmark,
            provider,
            config=cfg,
            params=par,
            variant=variant,
            run_id=rid,
            log_path=log_path,
        )
        eta.dump(eta_path)

        ref = consensus_reference(eta)
        kc = cohens_kappa(eta, ref)
        kf = fleiss_kappa(eta)
        cov_val = coverage(eta)
        n_agreement = sum(
            1
            for i, it in enumerate(eta.items)
            if it.model_verdict == ref(i)
        )

        rows.append(
            SweepRow(
                value=value,
                coverage=cov_val,
                kappa_c=kc,
                kappa_f=kf,
                n_agreement=n_agreement,
                n_total=eta.n,
                eta_path=eta_path,
            )
        )

    return SweepResult(parameter=parameter, rows=tuple(rows))


__all__ = [
    "SweepError",
    "SweepResult",
    "SweepRow",
    "coerce_values",
    "run_sweep",
]
