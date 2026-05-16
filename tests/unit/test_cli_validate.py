"""Tests for ``infereval validate`` CLI subcommand."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from infereval.cli.main import cli

REPO_ROOT = Path(__file__).resolve().parents[2]
STOP_SIGN_PATH = REPO_ROOT / "examples" / "stop_sign" / "benchmark.json"


class TestValidateBenchmark:
    def test_validates_committed_stop_sign(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(STOP_SIGN_PATH)])
        assert result.exit_code == 0, result.output
        assert "OK" in result.output
        assert "stop-sign-example-1" in result.output
        assert "m=1" in result.output
        assert "n=4" in result.output

    def test_quiet_suppresses_success_message(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--quiet", str(STOP_SIGN_PATH)])
        assert result.exit_code == 0
        assert result.output == ""

    def test_rejects_malformed_json(self, tmp_path: Path) -> None:
        bad = tmp_path / "not-json.json"
        bad.write_text("{ not valid json", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(bad)])
        assert result.exit_code == 2
        assert "not valid JSON" in result.output

    def test_rejects_benchmark_with_unknown_bearer(self, tmp_path: Path) -> None:
        # Load the valid example, then corrupt it.
        with STOP_SIGN_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data["items"][0]["premises"].append("ghost-bearer")
        bad = tmp_path / "broken.json"
        bad.write_text(json.dumps(data), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(bad)])
        assert result.exit_code == 1
        assert "failed benchmark validation" in result.output
        assert "unknown bearer ids" in result.output

    def test_rejects_missing_required_field(self, tmp_path: Path) -> None:
        with STOP_SIGN_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        del data["analysts"]
        bad = tmp_path / "broken.json"
        bad.write_text(json.dumps(data), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(bad)])
        assert result.exit_code == 1
        assert "validation error" in result.output


class TestValidateEvaluation:
    def _minimal_eval(self) -> dict:
        return {
            "schema_version": "1.0",
            "id": "run-0001",
            "benchmark_id": "stop-sign-example-1",
            "model": {"provider": "mock", "model_id": "test-v1"},
            "items": [
                {
                    "id": "row-0",
                    "premises": ["sa"],
                    "conclusions": ["ra"],
                    "analyst_verdicts": ["good"],
                    "model_verdict": "good",
                }
            ],
        }

    def test_validates_minimal_evaluation(self, tmp_path: Path) -> None:
        path = tmp_path / "eval.json"
        path.write_text(json.dumps(self._minimal_eval()), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--evaluation", str(path)])
        assert result.exit_code == 0, result.output
        assert "valid evaluation" in result.output
        assert "run-0001" in result.output

    def test_fails_when_using_wrong_kind_flag(self, tmp_path: Path) -> None:
        # An evaluation file validated as a benchmark should fail.
        path = tmp_path / "eval.json"
        path.write_text(json.dumps(self._minimal_eval()), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(path)])  # no --evaluation
        assert result.exit_code == 1
        assert "failed benchmark validation" in result.output

    def test_rejects_invalid_verdict_value(self, tmp_path: Path) -> None:
        data = self._minimal_eval()
        data["items"][0]["model_verdict"] = "maybe"
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--evaluation", str(path)])
        assert result.exit_code == 1
        assert "failed evaluation validation" in result.output


class TestCliWiring:
    def test_validate_appears_in_top_level_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "validate" in result.output

    def test_validate_has_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "--evaluation" in result.output
        assert "--quiet" in result.output
