"""Tests for ``infereval evaluate``.

Real providers are mocked out by patching :func:`infereval.cli.evaluate_cmd.get_provider`
to return a :class:`ScriptedProvider`.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from infereval.cli.main import cli
from infereval.evaluation import Evaluation
from infereval.providers.mock import ScriptedProvider
from infereval.types import Verdict

REPO_ROOT = Path(__file__).resolve().parents[2]
STOP_SIGN_PATH = REPO_ROOT / "examples" / "stop_sign" / "benchmark.json"


# ---- --dry-run --------------------------------------------------------------


class TestDryRun:
    def test_dry_run_no_provider_required(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["evaluate", str(STOP_SIGN_PATH), "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "Dry run" in result.output
        assert "default-v1" in result.output
        assert "## System prompt" in result.output
        # All four items should appear
        for rid in ("row-0", "row-1", "row-2", "row-3"):
            assert f"## Item {rid}" in result.output

    def test_dry_run_prompts_are_tex_stripped(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["evaluate", str(STOP_SIGN_PATH), "--dry-run"])
        # "$a$" should not appear; "a" should appear
        assert "$" not in result.output
        assert "a is a stop sign" in result.output


# ---- Full run with patched provider -----------------------------------------


class TestFullRun:
    def test_writes_evaluation_json(self, tmp_path: Path) -> None:
        out_path = tmp_path / "eta.json"
        # Schedule the model to match the paper's analyst row
        provider = ScriptedProvider(
            responses=["GOOD"] * 9 + ["BAD"] * 3,
            model_id="patched-mock-v1",
        )
        with patch(
            "infereval.cli.evaluate_cmd.get_provider", return_value=provider
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "evaluate",
                    str(STOP_SIGN_PATH),
                    "--provider", "anthropic",
                    "--model", "claude-opus-4-7",
                    "--output", str(out_path),
                    "--n-samples", "3",
                    "--temperature", "0.0",
                    "--max-tokens", "8",
                    "--run-id", "test-run-001",
                ],
            )
        assert result.exit_code == 0, result.output
        assert "OK: wrote" in result.output
        assert out_path.exists()

        eta = Evaluation.load(out_path)
        assert eta.id == "test-run-001"
        assert eta.benchmark_id == "stop-sign-example-1"
        assert eta.n == 4
        # The scripted responses produce GOOD for rows 0-2 and BAD for row-3
        assert eta.items[0].model_verdict == Verdict.GOOD
        assert eta.items[3].model_verdict == Verdict.BAD

    def test_records_provider_params(self, tmp_path: Path) -> None:
        out_path = tmp_path / "eta.json"
        provider = ScriptedProvider(responses=["GOOD"] * 50)
        with patch(
            "infereval.cli.evaluate_cmd.get_provider", return_value=provider
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "evaluate",
                    str(STOP_SIGN_PATH),
                    "--provider", "openai",
                    "--model", "gpt-4o-mini",
                    "--output", str(out_path),
                    "--n-samples", "2",
                    "--temperature", "0.3",
                    "--max-tokens", "16",
                    "--seed", "123",
                ],
            )
        assert result.exit_code == 0, result.output
        eta = Evaluation.load(out_path)
        assert eta.model.params.temperature == 0.3
        assert eta.model.params.max_tokens == 16
        assert eta.model.params.seed == 123
        assert eta.endorsement_config.n_samples == 2

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        out_path = tmp_path / "nested" / "dirs" / "eta.json"
        provider = ScriptedProvider(responses=["GOOD"] * 10)
        with patch(
            "infereval.cli.evaluate_cmd.get_provider", return_value=provider
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "evaluate", str(STOP_SIGN_PATH),
                    "--provider", "openai", "--model", "gpt-4o",
                    "--output", str(out_path), "--n-samples", "1",
                ],
            )
        assert result.exit_code == 0, result.output
        assert out_path.exists()


# ---- Argument validation ---------------------------------------------------


class TestArgValidation:
    def test_missing_provider_fails(self, tmp_path: Path) -> None:
        out_path = tmp_path / "eta.json"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["evaluate", str(STOP_SIGN_PATH), "--model", "x", "--output", str(out_path)],
        )
        assert result.exit_code == 2
        assert "--provider" in result.output and "required" in result.output

    def test_missing_model_fails(self, tmp_path: Path) -> None:
        out_path = tmp_path / "eta.json"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["evaluate", str(STOP_SIGN_PATH), "--provider", "openai", "--output", str(out_path)],
        )
        assert result.exit_code == 2
        assert "--model" in result.output

    def test_missing_output_fails(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["evaluate", str(STOP_SIGN_PATH), "--provider", "openai", "--model", "gpt"],
        )
        assert result.exit_code == 2
        assert "--output" in result.output

    def test_unknown_provider_choice_rejected_by_click(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["evaluate", str(STOP_SIGN_PATH), "--provider", "fake",
             "--model", "x", "--output", "/tmp/x.json"],
        )
        assert result.exit_code != 0
        # click prints the available choices
        assert "anthropic" in result.output

    def test_provider_config_error_surfaces_cleanly(self, tmp_path: Path) -> None:
        # Trigger a real ProviderConfigError by asking for anthropic without an API key.
        out_path = tmp_path / "eta.json"
        runner = CliRunner()
        # Make sure no anthropic key is present.
        result = runner.invoke(
            cli,
            [
                "evaluate", str(STOP_SIGN_PATH),
                "--provider", "anthropic",
                "--model", "claude-opus-4-7",
                "--output", str(out_path),
            ],
            env={"ANTHROPIC_API_KEY": ""},
        )
        assert result.exit_code == 2
        assert "provider configuration" in result.output


# ---- OpenRouter attribution headers ---------------------------------------


class TestOpenRouter:
    def test_openrouter_passes_attribution_headers(self, tmp_path: Path) -> None:
        out_path = tmp_path / "eta.json"
        captured_kwargs: dict[str, object] = {}

        def fake_get_provider(provider: str, model_id: str, **kwargs: object):
            captured_kwargs["provider"] = provider
            captured_kwargs.update(kwargs)
            return ScriptedProvider(responses=["GOOD"] * 10)

        with patch(
            "infereval.cli.evaluate_cmd.get_provider", side_effect=fake_get_provider
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "evaluate", str(STOP_SIGN_PATH),
                    "--provider", "openrouter",
                    "--model", "anthropic/claude-3.5-sonnet",
                    "--output", str(out_path),
                    "--n-samples", "1",
                    "--http-referer", "https://example.com",
                    "--x-title", "infereval-test",
                ],
            )
        assert result.exit_code == 0, result.output
        assert captured_kwargs["provider"] == "openrouter"
        assert captured_kwargs["http_referer"] == "https://example.com"
        assert captured_kwargs["x_title"] == "infereval-test"


# ---- Output validation ----------------------------------------------------


class TestOutputShape:
    def test_output_is_valid_evaluation_json(self, tmp_path: Path) -> None:
        out_path = tmp_path / "eta.json"
        provider = ScriptedProvider(responses=["GOOD"] * 10)
        with patch(
            "infereval.cli.evaluate_cmd.get_provider", return_value=provider
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "evaluate", str(STOP_SIGN_PATH),
                    "--provider", "openai", "--model", "gpt-4o-mini",
                    "--output", str(out_path),
                    "--n-samples", "1",
                ],
            )
        assert result.exit_code == 0
        # Re-validate via the validate subcommand
        v = runner.invoke(cli, ["validate", "--evaluation", str(out_path)])
        assert v.exit_code == 0, v.output

    def test_output_contains_benchmark_hash(self, tmp_path: Path) -> None:
        out_path = tmp_path / "eta.json"
        provider = ScriptedProvider(responses=["GOOD"] * 10)
        with patch(
            "infereval.cli.evaluate_cmd.get_provider", return_value=provider
        ):
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "evaluate", str(STOP_SIGN_PATH),
                    "--provider", "openai", "--model", "gpt-4o-mini",
                    "--output", str(out_path),
                    "--n-samples", "1",
                ],
            )
        with out_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["benchmark_hash"].startswith("sha256:")
