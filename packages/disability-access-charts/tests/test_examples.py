"""The examples run and do what their docstrings say."""

import json
import runpy
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def run(name: str, out: Path) -> int:
    module = runpy.run_path(str(EXAMPLES / f"{name}.py"))
    return module["main"](out)


def test_jonapwd_bar(tmp_path: Path) -> None:
    assert run("jonapwd_bar", tmp_path) == 0
    doc = json.loads((tmp_path / "jonapwd_bar.json").read_text(encoding="utf-8"))
    assert doc["audit"]["passed"] is True
    assert (tmp_path / "jonapwd_bar.table.html").exists()
    assert (tmp_path / "jonapwd_bar.csv").exists()


def test_dot_plot_shows_one_passing_and_one_rejected_claim(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("dot_plot_illustrative", tmp_path) == 0
    out = capsys.readouterr().out
    assert "PASSES the claim checker" in out
    assert "REJECTED (comparison)" in out
    doc = json.loads((tmp_path / "dot_plot_illustrative.json").read_text(encoding="utf-8"))
    assert "ILLUSTRATIVE" in doc["title"]


def test_audit_plotly_figure(tmp_path: Path) -> None:
    assert run("audit_plotly_figure", tmp_path) == 0
