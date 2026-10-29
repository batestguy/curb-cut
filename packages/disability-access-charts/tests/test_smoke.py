from pathlib import Path

import disability_access_charts
import pytest

try:
    import tomllib
except ImportError:  # Python 3.10: the package supports it, but CI runs 3.12 only
    tomllib = pytest.importorskip("tomli")

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version() -> None:
    assert disability_access_charts.__version__ == "0.2.0"


def test_version_matches_pyproject() -> None:
    # The publish workflow checks the tag against pyproject's version.
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    assert project["version"] == disability_access_charts.__version__


def test_core_does_not_import_plotly() -> None:
    import subprocess
    import sys

    code = "import sys, disability_access_charts; print('plotly' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
