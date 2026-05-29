"""v0.7.0 (closes #82) — dual rendering of κ_F* in the construct-validity
report's section 2 on panelled benchmarks.

On a panelled benchmark, the headline κ_F* is the all-analyst Fleiss
(the new v0.7.0 default), and the primary panel's κ_F* is rendered as
an indented sub-bullet so the methodological distinction (panels are
an additive convergent-validity device, not a replacement for the
baseline) is visible at the surface where the reader looks for the
Remark 4 number.

On a non-panelled benchmark, only the single headline κ_F* line
renders (unchanged from v0.6.x).
"""

from __future__ import annotations

import json
from pathlib import Path

from infereval.benchmark import Benchmark
from infereval.endorsement import EndorsementConfig
from infereval.evaluation import evaluate
from infereval.providers.mock import ScriptedProvider
from infereval.report import ConstructValidityClaims, render_markdown

STOP_SIGN_PATH = (
    Path(__file__).parent.parent.parent / "examples" / "stop_sign" / "benchmark.json"
)


def _make_panelled_bench_and_eta(
    primary_unanimous: bool,
) -> tuple[Benchmark, object]:
    """Stop-sign benchmark with 4 analysts and 2 panels (primary +
    reviewer). When ``primary_unanimous=True`` the primary panel
    agrees on every item (so its κ_F* would be +1.0 under the
    pre-v0.7.0 narrowing default) while the all-analyst κ_F* is
    materially lower because the reviewer panel disagrees on some
    items.
    """
    data = json.loads(STOP_SIGN_PATH.read_text())
    # Replace the single analyst with four, declaring two panels.
    base_verdicts = [it["analyst_verdicts"][0] for it in data["items"]]
    data["analysts"] = [
        {"id": "primary-a", "display_name": "Primary A", "panel": "primary"},
        {"id": "primary-b", "display_name": "Primary B", "panel": "primary"},
        {"id": "reviewer-a", "display_name": "Reviewer A", "panel": "reviewer"},
        {"id": "reviewer-b", "display_name": "Reviewer B", "panel": "reviewer"},
    ]
    data["primary_panel"] = "primary"
    flip = {"good": "bad", "bad": "good", "abstain": "abstain"}
    for i, it in enumerate(data["items"]):
        v = base_verdicts[i]
        primary_pair = (
            [v, v]
            if primary_unanimous
            else [v, flip[v] if i == 0 else v]
        )
        # Reviewer panel disagrees on the first two items to drag the
        # all-analyst figure down.
        reviewer_pair = [
            flip[v] if i < 2 else v,
            v,
        ]
        it["analyst_verdicts"] = [*primary_pair, *reviewer_pair]
    bench = Benchmark.model_validate(data)
    provider = ScriptedProvider(responses=["GOOD"] * 16)
    eta = evaluate(bench, provider, config=EndorsementConfig(n_samples=1))
    return bench, eta


def _make_unpanelled_bench_and_eta() -> tuple[Benchmark, object]:
    """2-analyst stop-sign with no panels declared — the non-panelled
    rendering path."""
    data = json.loads(STOP_SIGN_PATH.read_text())
    data["analysts"].append(
        {"id": "second", "display_name": "Second analyst"}
    )
    for it in data["items"]:
        it["analyst_verdicts"].append(it["analyst_verdicts"][0])
    bench = Benchmark.model_validate(data)
    provider = ScriptedProvider(responses=["GOOD"] * 8)
    eta = evaluate(bench, provider, config=EndorsementConfig(n_samples=1))
    return bench, eta


# ---- Tests ---------------------------------------------------------------


def test_panelled_benchmark_renders_both_headline_and_primary_subbullet() -> None:
    bench, eta = _make_panelled_bench_and_eta(primary_unanimous=True)
    claims = ConstructValidityClaims.stub()
    md = render_markdown(evaluation=eta, benchmark=bench, claims=claims)  # type: ignore[arg-type]

    # New headline: explicit "(all analysts)" qualifier.
    assert "Inter-analyst κ_F\\* (all analysts)" in md
    # Sub-bullet: the primary panel's κ_F* (the pre-v0.7.0 narrowing
    # value) renders as an indented italic line.
    assert "*Primary panel (`primary`) κ_F\\*" in md


def test_panelled_benchmark_headline_is_all_analyst_not_primary() -> None:
    """The headline κ_F* on a panelled benchmark is the all-analyst
    figure. When the primary panel is internally unanimous (κ_F* = +1.0
    on its own) and the reviewer panel disagrees with it, the
    all-analyst figure must be strictly less than the primary panel's
    value — that's the +1.0-when-unanimous-primary failure mode #82
    flagged."""
    bench, eta = _make_panelled_bench_and_eta(primary_unanimous=True)
    claims = ConstructValidityClaims.stub()
    md = render_markdown(evaluation=eta, benchmark=bench, claims=claims)  # type: ignore[arg-type]

    # Pick the headline line.
    headline = next(
        line for line in md.splitlines()
        if "Inter-analyst κ_F\\* (all analysts)" in line
    )
    # Pick the primary-panel sub-bullet line.
    sub = next(
        line for line in md.splitlines()
        if "*Primary panel" in line and "κ_F\\*" in line
    )

    # Parse the numeric values out (format: "+0.4567" or "undefined").
    def _extract_kappa(line: str) -> float | None:
        for tok in line.replace("*", " ").split():
            try:
                return float(tok)
            except ValueError:
                continue
        return None

    headline_v = _extract_kappa(headline)
    sub_v = _extract_kappa(sub)
    assert headline_v is not None
    assert sub_v is not None
    # The primary panel was constructed to be unanimous (κ_F* = +1.0);
    # the all-analyst headline must be strictly less than that.
    assert sub_v == 1.0
    assert headline_v < 1.0


def test_unpanelled_benchmark_renders_single_line_only() -> None:
    """Non-panelled benchmarks render the pre-v0.7.0 single headline
    line. No "(all analysts)" qualifier and no sub-bullet."""
    bench, eta = _make_unpanelled_bench_and_eta()
    claims = ConstructValidityClaims.stub()
    md = render_markdown(evaluation=eta, benchmark=bench, claims=claims)  # type: ignore[arg-type]

    # Headline uses the unmodified "Inter-analyst κ_F\*" label.
    assert "Inter-analyst κ_F\\*" in md
    # No "(all analysts)" qualifier on the non-panelled path.
    assert "Inter-analyst κ_F\\* (all analysts)" not in md
    # No "Primary panel" sub-bullet either.
    assert "Primary panel" not in md
