"""Tests for ``infereval.report`` — Phase 3.1 construct-validity report."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from infereval.benchmark import Benchmark
from infereval.evaluation import EndorsementConfig, evaluate
from infereval.providers.mock import ScriptedProvider
from infereval.report import (
    CompetingExplanationChecks,
    ConstructValidityClaims,
    compute_verdict,
    render_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STOP_SIGN_PATH = REPO_ROOT / "examples" / "stop_sign" / "benchmark.json"


def _minimal_claims(
    *,
    scope: str = "items_in_benchmark",
    **ce_overrides: bool,
) -> ConstructValidityClaims:
    return ConstructValidityClaims(
        mastery_sense={
            "sense": "evaluative",
            "description": "test claim",
        },
        scope={
            "scope": scope,
            "justification": "test scope",
        },
        constitution={
            "position": "evidence_of_mastery",
            "justification": "test",
        },
        carving={
            "acknowledges_carving_indexed": False,
            "notes": "",
        },
        competing_explanations=CompetingExplanationChecks(**ce_overrides),
    )


# ---- Schema ---------------------------------------------------------------


class TestClaimsSchema:
    def test_well_formed_claims_validate(self) -> None:
        c = _minimal_claims()
        assert c.scope.scope == "items_in_benchmark"

    def test_missing_required_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConstructValidityClaims.model_validate({
                "mastery_sense": {"sense": "evaluative"},  # missing description
                "scope": {"scope": "items_in_benchmark", "justification": "x"},
                "constitution": {"position": "evidence_of_mastery", "justification": "x"},
                "carving": {"acknowledges_carving_indexed": False, "notes": ""},
            })

    def test_invalid_literal_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConstructValidityClaims.model_validate({
                "mastery_sense": {"sense": "BOGUS", "description": "x"},
                "scope": {"scope": "items_in_benchmark", "justification": "x"},
                "constitution": {"position": "evidence_of_mastery", "justification": "x"},
                "carving": {"acknowledges_carving_indexed": False, "notes": ""},
            })

    def test_stub_has_all_required_fields(self) -> None:
        stub = ConstructValidityClaims.stub()
        json_text = stub.model_dump_json()
        # Parses back without error.
        reloaded = ConstructValidityClaims.model_validate(json.loads(json_text))
        assert reloaded.mastery_sense.sense == stub.mastery_sense.sense


# ---- Verdict computation --------------------------------------------------


class TestComputeVerdict:
    def test_all_required_checks_yields_defensible(self) -> None:
        claims = _minimal_claims(
            scope="items_in_benchmark",
            structural_check_run=True,
            sensitivity_sweep_run=True,
        )
        v = compute_verdict(claims)
        assert v.label == "defensible"

    def test_some_required_missing_yields_partial(self) -> None:
        claims = _minimal_claims(
            scope="items_in_benchmark",
            structural_check_run=True,  # 1 of 2 required for this scope
        )
        v = compute_verdict(claims)
        assert v.label == "partially_defensible"

    def test_majority_required_missing_yields_not_defensible(self) -> None:
        # general_capacity requires 8 checks; with none run, > half missing -> NOT.
        claims = _minimal_claims(scope="general_capacity")
        v = compute_verdict(claims)
        assert v.label == "not_defensible"

    def test_general_capacity_requires_carving_acknowledgement(self) -> None:
        # All 8 required checks run, but carving not acknowledged
        # at the general_capacity scope → NOT defensible (R19).
        claims = ConstructValidityClaims(
            mastery_sense={"sense": "standing", "description": "x"},
            scope={"scope": "general_capacity", "justification": "x"},
            constitution={"position": "evidence_of_mastery", "justification": "x"},
            carving={"acknowledges_carving_indexed": False, "notes": ""},
            competing_explanations=CompetingExplanationChecks(
                structural_check_run=True,
                sensitivity_sweep_run=True,
                paraphrase_sweep_run=True,
                cross_panel_check_run=True,
                held_out_items_used=True,
                training_data_separation_verified=True,
                cross_domain_comparison_run=True,
                replication_attempted=True,
            ),
        )
        v = compute_verdict(claims)
        assert v.label == "not_defensible"
        assert "carving" in " ".join(v.rationale).lower()

    def test_general_capacity_carving_with_empty_notes_still_fails_r19(self) -> None:
        claims = ConstructValidityClaims(
            mastery_sense={"sense": "standing", "description": "x"},
            scope={"scope": "general_capacity", "justification": "x"},
            constitution={"position": "evidence_of_mastery", "justification": "x"},
            carving={"acknowledges_carving_indexed": True, "notes": ""},
            competing_explanations=CompetingExplanationChecks(
                structural_check_run=True,
                sensitivity_sweep_run=True,
                paraphrase_sweep_run=True,
                cross_panel_check_run=True,
                held_out_items_used=True,
                training_data_separation_verified=True,
                cross_domain_comparison_run=True,
                replication_attempted=True,
            ),
        )
        v = compute_verdict(claims)
        assert v.label == "not_defensible"

    def test_general_capacity_fully_satisfied_is_defensible(self) -> None:
        claims = ConstructValidityClaims(
            mastery_sense={"sense": "standing", "description": "x"},
            scope={"scope": "general_capacity", "justification": "x"},
            constitution={"position": "evidence_of_mastery", "justification": "x"},
            carving={
                "acknowledges_carving_indexed": True,
                "notes": "Documented in §4.",
            },
            competing_explanations=CompetingExplanationChecks(
                structural_check_run=True,
                sensitivity_sweep_run=True,
                paraphrase_sweep_run=True,
                cross_panel_check_run=True,
                held_out_items_used=True,
                training_data_separation_verified=True,
                cross_domain_comparison_run=True,
                replication_attempted=True,
            ),
        )
        assert compute_verdict(claims).label == "defensible"


# ---- Markdown rendering ---------------------------------------------------


class TestMarkdownRendering:
    def _bench_and_eta(self) -> tuple[Benchmark, object]:  # type: ignore[type-arg]
        bench = Benchmark.load(STOP_SIGN_PATH)
        provider = ScriptedProvider(responses=["GOOD"] * 12)
        eta = evaluate(
            bench, provider, config=EndorsementConfig(n_samples=1)
        )
        return bench, eta

    def test_report_contains_all_sections(self) -> None:
        bench, eta = self._bench_and_eta()
        md = render_markdown(
            evaluation=eta,  # type: ignore[arg-type]
            benchmark=bench,
            claims=_minimal_claims(),
        )
        assert "# Construct-validity report" in md
        assert "## 1. Identity" in md
        assert "## 2. Summary metrics" in md
        assert "## 3. Construct-validity claims" in md
        assert "## 4. Evidence" in md
        assert "## 5. Unaddressed competing explanations" in md
        assert "## 6. Summary verdict" in md

    def test_report_lists_unaddressed_checks(self) -> None:
        bench, eta = self._bench_and_eta()
        md = render_markdown(
            evaluation=eta,  # type: ignore[arg-type]
            benchmark=bench,
            claims=_minimal_claims(),  # no checks run
        )
        assert "paraphrase_sweep_run" in md
        assert "cross_panel_check_run" in md

    def test_report_integrates_structure_evidence_when_supplied(self) -> None:
        bench, eta = self._bench_and_eta()
        structure_report = {"total_anomalies": 0, "checks": []}
        md = render_markdown(
            evaluation=eta,  # type: ignore[arg-type]
            benchmark=bench,
            claims=_minimal_claims(structural_check_run=True),
            structure_report=structure_report,
        )
        assert "0 anomalies flagged" in md
        # NOT SUPPLIED line for structure should be replaced.
        assert "Structural coherence checks** (R13): NOT SUPPLIED" not in md

    def test_report_shows_not_supplied_for_missing_evidence(self) -> None:
        bench, eta = self._bench_and_eta()
        md = render_markdown(
            evaluation=eta,  # type: ignore[arg-type]
            benchmark=bench,
            claims=_minimal_claims(),
        )
        assert "Structural coherence checks** (R13): NOT SUPPLIED" in md
        assert "Sensitivity sweep** (R11): NOT SUPPLIED" in md
        assert "Factor-effects model fit** (R7, R12): NOT SUPPLIED" in md

    def test_summary_verdict_renders_with_badge(self) -> None:
        bench, eta = self._bench_and_eta()
        # All required checks run → defensible badge.
        md = render_markdown(
            evaluation=eta,  # type: ignore[arg-type]
            benchmark=bench,
            claims=_minimal_claims(
                structural_check_run=True,
                sensitivity_sweep_run=True,
            ),
        )
        assert "✅" in md
        assert "defensible" in md.lower()


# ---- CLI ------------------------------------------------------------------


class TestReportCLI:
    def test_init_claims_writes_stub(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from infereval.cli.main import cli

        target = tmp_path / "claims.json"
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "--init-claims", str(target)])
        assert result.exit_code == 0, result.output
        assert target.exists()
        # Stub parses as a valid claims file.
        data = json.loads(target.read_text(encoding="utf-8"))
        claims = ConstructValidityClaims.model_validate(data)
        assert claims.mastery_sense.sense == "evaluative"

    def test_full_report_against_stop_sign(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from infereval.cli.main import cli

        # First produce an evaluation file via the test fixture pattern.
        bench = Benchmark.load(STOP_SIGN_PATH)
        provider = ScriptedProvider(responses=["GOOD"] * 12)
        eta = evaluate(bench, provider, config=EndorsementConfig(n_samples=1))
        eta_path = tmp_path / "eta.json"
        eta.dump(eta_path)

        claims_path = tmp_path / "claims.json"
        claims_path.write_text(_minimal_claims().model_dump_json(), encoding="utf-8")

        out_path = tmp_path / "report.md"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "report",
            "--evaluation", str(eta_path),
            "--benchmark", str(STOP_SIGN_PATH),
            "--claims", str(claims_path),
            "-o", str(out_path),
        ])
        assert result.exit_code == 0, result.output
        text = out_path.read_text(encoding="utf-8")
        assert "Construct-validity report" in text
        assert "Mastery claim" in text

    def test_missing_required_inputs_errors(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from infereval.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["report"])
        assert result.exit_code != 0
        assert "required" in result.output.lower()

    def test_mismatched_benchmark_id_rejected(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from infereval.cli.main import cli

        bench = Benchmark.load(STOP_SIGN_PATH)
        provider = ScriptedProvider(responses=["GOOD"] * 12)
        eta = evaluate(bench, provider, config=EndorsementConfig(n_samples=1))
        eta_path = tmp_path / "eta.json"
        eta.dump(eta_path)

        # Write a different benchmark with id "other".
        other = bench.model_copy(update={"id": "other-bench"})
        other_path = tmp_path / "other.json"
        other.dump(other_path)

        claims_path = tmp_path / "claims.json"
        claims_path.write_text(_minimal_claims().model_dump_json(), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(cli, [
            "report",
            "--evaluation", str(eta_path),
            "--benchmark", str(other_path),
            "--claims", str(claims_path),
        ])
        assert result.exit_code != 0
        assert "benchmark_id" in result.output
