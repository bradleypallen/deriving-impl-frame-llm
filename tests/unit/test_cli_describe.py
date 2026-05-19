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


class TestDescribeNewSections:
    """Issue #25: bearers, verification prompt, references, group cross-tab."""

    def test_bearers_section_lists_all_with_expressions(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(STOP_SIGN_PATH)])
        assert "bearers (5):" in result.output
        # Each stop-sign bearer id + its expression should appear.
        # ('a' is rendered in the expression as $a$; just check the substantive words.)
        assert "is a stop sign" in result.output
        assert "is red" in result.output
        assert "nighttime" in result.output

    def test_header_columns_align(self) -> None:
        # id / title / domain / schema all use the same 13-char label column.
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(STOP_SIGN_PATH)])
        # Each header label is followed by enough spaces to reach column 13.
        # "id:" is 3 chars -> 10 spaces; "title:" is 6 -> 7 spaces; etc.
        assert "id:          stop-sign-example-1" in result.output
        assert "schema:      1.0" in result.output

    def test_verification_prompt_section_renders_when_override_present(
        self, tmp_path: Path
    ) -> None:
        # Synthesise a benchmark with an embedded verification prompt override.
        data = {
            "schema_version": "1.0",
            "id": "vp-test",
            "bearers": {"p": {"expression": "P"}, "q": {"expression": "Q"}},
            "analysts": [{"id": "a"}],
            "verification_prompt": {
                "template": "Premises: {premise_context}\nConclusion: {conclusion_context}\nVerdict:",
                "system": "You are a careful evaluator.",
                "parse_regex": "\\b(GOOD|BAD|ABSTAIN)\\b",
                "id": "my-prompt-v1",
            },
            "items": [
                {"id": "i1", "premises": ["p"], "conclusions": ["q"], "analyst_verdicts": ["good"]},
            ],
        }
        path = tmp_path / "vp.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(path)])
        assert "verification prompt:" in result.output
        assert "my-prompt-v1" in result.output
        assert "careful evaluator" in result.output
        assert "GOOD|BAD|ABSTAIN" in result.output

    def test_verification_prompt_section_omitted_when_no_override(self) -> None:
        # The stop-sign benchmark uses the framework default — no override.
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(STOP_SIGN_PATH)])
        assert "verification prompt:" not in result.output

    def test_references_section_omitted_when_no_refs_present(self) -> None:
        # Stop-sign benchmark predates v0.2.2 and has no references field
        # populated — the references section must not appear.
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(STOP_SIGN_PATH)])
        assert "references:" not in result.output

    def test_references_section_renders_when_refs_present(self, tmp_path: Path) -> None:
        data = {
            "schema_version": "1.0",
            "id": "refs-test",
            "bearers": {
                "p": {"expression": "P", "references": ["Bearer-level ref"]},
                "q": {"expression": "Q"},
            },
            "analysts": [{"id": "a"}],
            "items": [
                {
                    "id": "i1",
                    "premises": ["p"],
                    "conclusions": ["q"],
                    "analyst_verdicts": ["good"],
                    "references": [
                        {"citation": "Item ref 1", "doi": "10.1/foo"},
                        "Item ref 2",
                    ],
                },
            ],
            "references": [
                {"citation": "Corpus ref alpha", "doi": "10.0/a"},
                "Corpus ref beta",
            ],
        }
        path = tmp_path / "refs.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(path)])
        assert "references:" in result.output
        assert "benchmark-level: 2" in result.output
        assert "bearer-level:    1 (across 1/2 bearers)" in result.output
        assert "item-level:      2 references across 1/1 items" in result.output
        assert "Corpus ref alpha" in result.output
        assert "Corpus ref beta" in result.output

    def test_group_cross_tab_renders_for_pulmonology_style_tags(
        self, tmp_path: Path
    ) -> None:
        # Synthesise a 3-item benchmark with T1, T2, cross-cutting tags.
        data = {
            "schema_version": "1.0",
            "id": "groups-test",
            "bearers": {"p": {"expression": "P"}, "q": {"expression": "Q"}},
            "analysts": [{"id": "a"}],
            "items": [
                {
                    "id": "i1",
                    "premises": ["p"],
                    "conclusions": ["q"],
                    "analyst_verdicts": ["good"],
                    "tags": ["supporter", "T1", "dialectical-low"],
                },
                {
                    "id": "i2",
                    "premises": ["p"],
                    "conclusions": ["q"],
                    "analyst_verdicts": ["bad"],
                    "tags": ["defeater", "T2", "dialectical-medium"],
                },
                {
                    "id": "i3",
                    "premises": ["p"],
                    "conclusions": ["q"],
                    "analyst_verdicts": ["good"],
                    "tags": ["cross-cutting", "marker-inference"],
                },
            ],
        }
        path = tmp_path / "groups.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(path)])
        assert "verdict distribution by tag group" in result.output
        # T1 / T2 / cross-cutting all present with their verdict counts.
        assert "T1" in result.output
        assert "T2" in result.output
        assert "cross-cutting" in result.output
        # T1 should sort before T2 should sort before cross-cutting.
        idx_t1 = result.output.index("\n  T1")
        idx_t2 = result.output.index("\n  T2")
        idx_cc = result.output.index("\n  cross-cutting")
        assert idx_t1 < idx_t2 < idx_cc

    def test_group_cross_tab_omitted_when_no_recognised_groups(
        self, tmp_path: Path
    ) -> None:
        # An item with only inference-role tags (no T1/T2/cross-cutting)
        # produces no informative grouping; the section is skipped.
        data = {
            "schema_version": "1.0",
            "id": "no-groups",
            "bearers": {"p": {"expression": "P"}, "q": {"expression": "Q"}},
            "analysts": [{"id": "a"}],
            "items": [
                {
                    "id": "i1",
                    "premises": ["p"],
                    "conclusions": ["q"],
                    "analyst_verdicts": ["good"],
                    "tags": ["custom-tag"],
                },
            ],
        }
        path = tmp_path / "no-groups.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(path)])
        assert "verdict distribution by tag group" not in result.output


class TestDescribeItemsFlag:
    """Issue #28: ``--items`` adds an expert-readable item listing."""

    PULM_PATH = REPO_ROOT / "examples" / "pulmonary_edema" / "benchmark.json"

    def test_default_omits_items_section(self) -> None:
        # The summary output must not change when --items is not supplied.
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", str(STOP_SIGN_PATH)])
        assert "items (" not in result.output
        # Implication-rendering markers should also be absent.
        assert " ⊢? " not in result.output

    def test_items_flag_emits_items_section_header(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", "--items", str(STOP_SIGN_PATH)])
        assert result.exit_code == 0, result.output
        assert "items (4):" in result.output

    def test_items_renders_resolved_premises_and_conclusion(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", "--items", str(STOP_SIGN_PATH)])
        # Γ and Δ labels visible.
        assert "Γ:" in result.output
        assert "Δ:" in result.output
        # The stop-sign expressions appear.
        assert "is a stop sign" in result.output
        assert "is red" in result.output

    def test_items_renders_verdict_and_tag_annotation(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", "--items", str(STOP_SIGN_PATH)])
        assert "→  good" in result.output
        assert "→  bad" in result.output
        # Stop-sign tags include irrelevant-addition; the bracketed annotation
        # uses this exact form.
        assert "[base-inference]" in result.output or "[irrelevant-addition]" in result.output

    def test_items_renders_inline_references_when_present(self) -> None:
        # Pulmonology benchmark carries item-level references.
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", "--items", str(self.PULM_PATH)])
        assert "references (" in result.output
        assert "doi:" in result.output
        assert "note:" in result.output
        assert "Ware LB, Matthay MA (2005)" in result.output
        # The a9 FLAG carries through.
        assert "FLAG FOR PULMONOLOGIST REVIEW" in result.output

    def test_items_groups_by_target_when_tags_present(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", "--items", str(self.PULM_PATH)])
        assert "T1 (12 items):" in result.output
        assert "T2 (10 items):" in result.output
        assert "cross-cutting (7 items):" in result.output
        # T1 group sorts before T2 sorts before cross-cutting.
        idx_t1 = result.output.index("T1 (12 items):")
        idx_t2 = result.output.index("T2 (10 items):")
        idx_cc = result.output.index("cross-cutting (7 items):")
        assert idx_t1 < idx_t2 < idx_cc

    def test_items_flat_layout_when_no_target_tags(self, tmp_path: Path) -> None:
        # Items with only inference-role tags should render as a flat block
        # (no T1/T2/cross-cutting headers).
        data = {
            "schema_version": "1.0",
            "id": "flat-items",
            "bearers": {"p": {"expression": "P holds"}, "q": {"expression": "Q follows"}},
            "analysts": [{"id": "a"}],
            "items": [
                {
                    "id": "i1",
                    "premises": ["p"],
                    "conclusions": ["q"],
                    "analyst_verdicts": ["good"],
                    "tags": ["custom-tag"],
                },
            ],
        }
        path = tmp_path / "flat.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", "--items", str(path)])
        assert "items (1):" in result.output
        assert "T1" not in result.output
        assert "P holds" in result.output
        assert "Q follows" in result.output

    def test_items_renders_multi_analyst_verdict_tuple(self, tmp_path: Path) -> None:
        data = {
            "schema_version": "1.0",
            "id": "multi-an",
            "bearers": {"p": {"expression": "P"}, "q": {"expression": "Q"}},
            "analysts": [{"id": "a"}, {"id": "b"}],
            "items": [
                {
                    "id": "i1",
                    "premises": ["p"],
                    "conclusions": ["q"],
                    "analyst_verdicts": ["good", "bad"],
                },
            ],
        }
        path = tmp_path / "multi.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["describe", "--items", str(path)])
        # Multi-analyst verdict tuple visible on the header line.
        assert "→  good, bad" in result.output


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
