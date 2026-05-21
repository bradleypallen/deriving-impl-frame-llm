"""End-to-end tests for analyst_rationales propagation + describe rendering.

Covers AR8 (carry-through to EvaluationItem), AR9 (hash coverage), AR2
(regression: metric paths untouched), AR11 (describe rendering and the
divergence-with-rationales flag), and AR12 (evaluation round-trip).

The benchmark-side validation and round-trip tests live in
``test_benchmark_io.py::TestAnalystRationales``.
"""

from __future__ import annotations

from click.testing import CliRunner

from infereval.benchmark import Benchmark
from infereval.evaluation import EndorsementConfig, canonical_benchmark_hash, evaluate
from infereval.metrics import (
    cohens_kappa,
    consensus_reference,
    coverage,
    fleiss_kappa,
    inter_analyst_fleiss,
)
from infereval.providers.mock import ScriptedProvider


def _bench_dict(*, with_rationales: bool, divergent: bool = False) -> dict:
    """Build a 2-item, 2-analyst benchmark, optionally with rationales.

    When ``divergent`` is True, the analysts disagree on i2 — useful for
    the AR11 disagreement-flag test.
    """
    a_verdicts_i2 = ["good", "bad"] if divergent else ["good", "good"]
    items = [
        {
            "id": "i1",
            "premises": ["p"],
            "conclusions": ["q"],
            "analyst_verdicts": ["good", "good"],
        },
        {
            "id": "i2",
            "premises": ["p", "r"],
            "conclusions": ["q"],
            "analyst_verdicts": a_verdicts_i2,
        },
    ]
    if with_rationales:
        items[0]["analyst_rationales"] = ["P is sufficient", "agreed"]
        items[1]["analyst_rationales"] = (
            ["P still sufficient", "R defeats it"]
            if divergent
            else ["", "no comment"]
        )
    return {
        "schema_version": "1.0",
        "id": "rationale-prop-test",
        "bearers": {
            "p": {"expression": "P"},
            "q": {"expression": "Q"},
            "r": {"expression": "R"},
        },
        "analysts": [{"id": "a"}, {"id": "b"}],
        "items": items,
    }


def _eta(bench: Benchmark):
    """Evaluate the 2-item bench against a scripted GOOD/GOOD provider."""
    provider = ScriptedProvider(responses=["GOOD"] * 8)
    return evaluate(bench, provider, config=EndorsementConfig(n_samples=1))


# ---- AR8: propagation from benchmark item into evaluation item ----------


class TestPropagationToEvaluation:
    def test_rationales_carry_through_to_evaluation_item(self) -> None:
        bench = Benchmark.model_validate(_bench_dict(with_rationales=True))
        eta = _eta(bench)
        assert eta.items[0].analyst_rationales == ["P is sufficient", "agreed"]
        # Empty-string entry survives.
        assert eta.items[1].analyst_rationales == ["", "no comment"]

    def test_absent_rationales_become_none_in_evaluation(self) -> None:
        bench = Benchmark.model_validate(_bench_dict(with_rationales=False))
        eta = _eta(bench)
        for item in eta.items:
            assert item.analyst_rationales is None

    def test_evaluation_item_round_trip_preserves_rationales(self) -> None:
        """AR12 applied to the evaluation artifact."""
        bench = Benchmark.model_validate(_bench_dict(with_rationales=True))
        eta = _eta(bench)
        json_out = eta.model_dump_json(exclude_none=True)
        eta2 = type(eta).model_validate_json(json_out)
        assert eta2.items[0].analyst_rationales == ["P is sufficient", "agreed"]
        assert eta2.items[1].analyst_rationales == ["", "no comment"]


# ---- AR9: rationales are covered by the benchmark_hash ------------------


class TestHashCoverage:
    def test_hash_changes_when_rationale_text_changes(self) -> None:
        bench_a = Benchmark.model_validate(_bench_dict(with_rationales=True))
        # Mutate the rationale text on one item.
        d = _bench_dict(with_rationales=True)
        d["items"][0]["analyst_rationales"] = ["different reason", "agreed"]
        bench_b = Benchmark.model_validate(d)
        assert canonical_benchmark_hash(bench_a) != canonical_benchmark_hash(bench_b)

    def test_hash_changes_when_rationales_added(self) -> None:
        bench_a = Benchmark.model_validate(_bench_dict(with_rationales=False))
        bench_b = Benchmark.model_validate(_bench_dict(with_rationales=True))
        assert canonical_benchmark_hash(bench_a) != canonical_benchmark_hash(bench_b)

    def test_hash_unchanged_when_no_rationales(self) -> None:
        """Backwards compat for the hash: adding the (None-valued) field
        to the model must not change the hash for existing benchmarks.
        exclude_none=True in canonical_benchmark_hash gives us this."""
        bench_a = Benchmark.model_validate(_bench_dict(with_rationales=False))
        # Idempotent: same input dict, two benchmarks, same hash.
        bench_b = Benchmark.model_validate(_bench_dict(with_rationales=False))
        assert canonical_benchmark_hash(bench_a) == canonical_benchmark_hash(bench_b)


# ---- AR2: regression — metric outputs are unaffected by rationales -----


class TestMetricsRegressionAR2:
    """The whole point of additivity: adding rationales must not change
    any number the metric/structure code computes. This test runs the
    same evaluation twice — once with rationales, once without — and
    asserts every coverage / kappa value is byte-identical.
    """

    def test_metrics_byte_identical_with_and_without_rationales(self) -> None:
        bench_no = Benchmark.model_validate(_bench_dict(with_rationales=False))
        bench_with = Benchmark.model_validate(_bench_dict(with_rationales=True))

        eta_no = _eta(bench_no)
        eta_with = _eta(bench_with)

        # coverage
        assert coverage(eta_no) == coverage(eta_with)

        # κ_C against consensus
        cons_no = consensus_reference(eta_no)
        cons_with = consensus_reference(eta_with)
        assert cohens_kappa(eta_no, cons_no) == cohens_kappa(eta_with, cons_with)

        # κ_F (model + all analysts)
        assert fleiss_kappa(eta_no) == fleiss_kappa(eta_with)

        # κ_F* (analysts only)
        assert inter_analyst_fleiss(bench_no) == inter_analyst_fleiss(bench_with)

    def test_structure_check_outputs_unaffected(self) -> None:
        from infereval.structure import run_all_checks

        bench_no = Benchmark.model_validate(_bench_dict(with_rationales=False))
        bench_with = Benchmark.model_validate(_bench_dict(with_rationales=True))
        eta_no = _eta(bench_no)
        eta_with = _eta(bench_with)

        rep_no = run_all_checks(eta_no, bench_no)
        rep_with = run_all_checks(eta_with, bench_with)

        # Same structure check outcomes (item counts, satisfying counts,
        # anomalies) regardless of whether rationales are present.
        for c_no, c_with in zip(rep_no.checks, rep_with.checks, strict=True):
            assert c_no.name == c_with.name
            assert c_no.items_checked == c_with.items_checked
            assert c_no.items_satisfying == c_with.items_satisfying
            assert len(c_no.anomalies) == len(c_with.anomalies)


# ---- AR11: describe --items rendering + divergence flag ------------------


class TestDescribeRationaleRendering:
    def _write_bench(self, tmp_path, d: dict):
        import json
        p = tmp_path / "bench.json"
        p.write_text(json.dumps(d), encoding="utf-8")
        return p

    def _invoke_describe(self, bench_path):
        from infereval.cli.main import cli
        runner = CliRunner()
        return runner.invoke(cli, ["describe", "--items", str(bench_path)])

    def test_rendering_skipped_when_no_rationales(self, tmp_path) -> None:
        """AR11 backwards-compat: a rationale-free benchmark's describe
        output should look exactly like it did before — no rationales
        section, no divergence flag."""
        path = self._write_bench(tmp_path, _bench_dict(with_rationales=False))
        result = self._invoke_describe(path)
        assert result.exit_code == 0
        assert "rationales:" not in result.output
        assert "disagreement+rationales" not in result.output

    def test_rendering_shows_each_analyst_rationale(self, tmp_path) -> None:
        path = self._write_bench(tmp_path, _bench_dict(with_rationales=True))
        result = self._invoke_describe(path)
        assert result.exit_code == 0
        assert "rationales:" in result.output
        # Each analyst id appears in the rationale block of its item.
        assert "a: P is sufficient" in result.output
        assert "b: agreed" in result.output

    def test_empty_string_entry_renders_as_no_reason_recorded(self, tmp_path) -> None:
        path = self._write_bench(tmp_path, _bench_dict(with_rationales=True))
        result = self._invoke_describe(path)
        # i2 has an empty rationale for analyst 'a' in the non-divergent
        # configuration; verify the visible label distinguishes it from
        # the absent-field case (which renders no rationales section).
        assert "(no reason recorded)" in result.output

    def test_divergence_flag_fires_when_verdicts_disagree_with_rationales(self, tmp_path) -> None:
        path = self._write_bench(
            tmp_path, _bench_dict(with_rationales=True, divergent=True)
        )
        result = self._invoke_describe(path)
        assert result.exit_code == 0
        # The flag is on the header line of the disagreement item (i2).
        assert "disagreement+rationales" in result.output
        # And i2's rationales are visible to support the triage.
        assert "P still sufficient" in result.output
        assert "R defeats it" in result.output

    def test_divergence_flag_silent_when_no_rationales(self, tmp_path) -> None:
        """The flag is a triage signal, not a generic 'analysts
        disagree' marker. Without rationales there's nothing to triage,
        so the flag stays off (consistent with the AR11 contract)."""
        path = self._write_bench(
            tmp_path, _bench_dict(with_rationales=False, divergent=True)
        )
        result = self._invoke_describe(path)
        assert result.exit_code == 0
        assert "disagreement+rationales" not in result.output
