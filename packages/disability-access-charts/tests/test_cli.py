import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from disability_access_charts import bar
from disability_access_charts.cli import main

KW: dict[str, Any] = {"title": "T", "value_label": "V", "category_label": "C", "source": "S"}


def write(path: Path, doc: object) -> Path:
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_passing_chart_exits_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write(tmp_path / "ok.json", bar(["A", "B"], [2, 1], **KW))
    assert main(["check", str(path)]) == 0
    assert "passed" in capsys.readouterr().out


def test_failing_chart_exits_1_and_explains(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = bar(["A", "B"], [2, 1], **KW)
    doc["alt_text"] = doc["alt_text"].replace("Largest: A", "Largest: B")
    path = write(tmp_path / "bad.json", doc)
    assert main(["check", str(path)]) == 1
    out = capsys.readouterr().out
    assert "FAILED" in out and "alt-text-matches-data" in out and "B is not the largest" in out


def test_strict_fails_on_warnings(tmp_path: Path) -> None:
    doc = bar(["A", "B"], [2, 1], **KW)
    doc["alt_text"] += " A exceeds B."
    path = write(tmp_path / "warn.json", doc)
    assert main(["check", str(path)]) == 0
    assert main(["check", "--strict", str(path)]) == 1


def test_unreadable_file_exits_2(tmp_path: Path) -> None:
    (tmp_path / "x.json").write_text("{not json", encoding="utf-8")
    assert main(["check", str(tmp_path / "x.json")]) == 2
    assert main(["check", str(tmp_path / "missing.json")]) == 2


def test_python_dash_m(tmp_path: Path) -> None:
    path = write(tmp_path / "ok.json", bar(["A", "B"], [2, 1], **KW))
    result = subprocess.run(
        [sys.executable, "-m", "disability_access_charts", "check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
