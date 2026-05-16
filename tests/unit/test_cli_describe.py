"""Tests for ``infereval describe``."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from click.testing import CliRunner

from infereval.cli.main import cli

REPO_ROOT = Path(__file__).resolve().parents[2]
STOP_SIGN_PATH = REPO_ROOT / "examples" / "stop_sign" / "benchmark.json"


class TestDescribeStopSign:
    def test_prints_id_title_domain(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(STOP_SIGN_PATH)])
        assert result.exit_code == 0, result.output
        assert "stop-sign-example-1" in result.output
        assert "Stop-sign RSR" in result.output
        assert "everyday-physical-objects" in result.output

    def test_prints_counts(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(STOP_SIGN_PATH)])
        assert "|B| (bearers):  5" in result.output
        assert "n (items):      4" in result.output
        assert "m (analysts):   1" in result.output

    def test_prints_analyst_distribution(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(STOP_SIGN_PATH)])
        # paper-author: 3 good, 1 bad
        assert "paper-author" in result.output
        assert "g=3" in result.output
        assert "b=1" in result.output

    def test_kappa_f_star_undefined_at_m_one(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(STOP_SIGN_PATH)])
        assert "κ_F*(β)" in result.output
        assert "undefined" in result.output
        assert "requires m ≥ 2 analysts" in result.output

    def test_prints_tags_and_rsr_target(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(STOP_SIGN_PATH)])
        assert "Tags:" in result.output
        assert "irrelevant-addition: 2" in result.output
        assert "RSR-targeted items: 4 / 4" in result.output
        assert "⟨{sa}, {ra}⟩: 4" in result.output


class TestDescribeMultiAnalyst:
    def test_kappa_f_star_defined_when_m_geq_2(self, tmp_path: Path) -> None:
        # Synthesize a 2-analyst, 4-item benchmark where the analysts agree
        # 3/4 times -> κ_F* is defined.
        data = {
            "schema_version": "1.0",
            "id": "synthetic-m2",
            "bearers": {
                "p": {"expression": "p"},
                "q": {"expression": "q"},
            },
            "analysts": [
                {"id": "a1"},
                {"id": "a2"},
            ],
            "items": [
                {"id": "i1", "premises": ["p"], "conclusions": ["q"], "analyst_verdicts": ["good", "good"]},
                {"id": "i2", "premises": ["p"], "conclusions": ["q"], "analyst_verdicts": ["good", "good"]},
                {"id": "i3", "premises": ["p"], "conclusions": ["q"], "analyst_verdicts": ["bad", "bad"]},
                {"id": "i4", "premises": ["p"], "conclusions": ["q"], "analyst_verdicts": ["good", "bad"]},
            ],
        }
        path = tmp_path / "synthetic.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(path)])
        assert result.exit_code == 0, result.output
        assert "m (analysts):   2" in result.output
        # κ_F* should be a numeric value (not "undefined")
        assert "κ_F*(β) (inter-analyst baseline):" in result.output
        kappa_line = next(
            line for line in result.output.splitlines() if line.startswith("κ_F*(β)")
        )
        assert "undefined" not in kappa_line

    def test_kappa_f_star_undefined_when_unanimous(self, tmp_path: Path) -> None:
        data = {
            "schema_version": "1.0",
            "id": "synthetic-unanimous",
            "bearers": {"p": {"expression": "p"}, "q": {"expression": "q"}},
            "analysts": [{"id": "a1"}, {"id": "a2"}],
            "items": [
                {"id": "i1", "premises": ["p"], "conclusions": ["q"], "analyst_verdicts": ["good", "good"]},
                {"id": "i2", "premises": ["p"], "conclusions": ["q"], "analyst_verdicts": ["good", "good"]},
            ],
        }
        path = tmp_path / "unan.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(path)])
        assert "undefined" in result.output
        assert "unanimous or all-non-substantive" in result.output


class TestDescribeFailures:
    def test_missing_file(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", "/nope/does/not/exist.json"])
        assert result.exit_code != 0

    def test_malformed_benchmark(self, tmp_path: Path) -> None:
        # Corrupt the stop-sign example by removing required fields
        with STOP_SIGN_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        d = copy.deepcopy(data)
        del d["analysts"]
        path = tmp_path / "broken.json"
        path.write_text(json.dumps(d), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(path)])
        assert result.exit_code != 0
