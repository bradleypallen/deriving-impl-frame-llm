"""Smoke tests for M0: package imports, version is exposed, CLI reports version."""

from __future__ import annotations

import subprocess
import sys

from click.testing import CliRunner

import infereval
from infereval.cli.main import cli


def test_version_is_string() -> None:
    assert isinstance(infereval.__version__, str)
    assert infereval.__version__


def test_cli_version_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert infereval.__version__ in result.output


def test_cli_entry_point_installed() -> None:
    """The `infereval` console script is installed and reports the version."""
    result = subprocess.run(
        [sys.executable, "-m", "infereval.cli.main", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert infereval.__version__ in result.stdout
