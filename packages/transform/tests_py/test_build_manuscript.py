"""Tests for the P5 journal manuscript (``scripts/build_manuscript.py``).

Built from the same synthetic fixture payload as the poverty page's tests, so no real
result is used and the tests run in CI's python job. CI's data job also runs
``build_manuscript.py --check`` against the real exported estimates.
"""

from __future__ import annotations

import copy
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "packages" / "transform" / "scripts"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ms = _load("build_manuscript", SCRIPTS / "build_manuscript.py")
pages = _load("test_build_poverty_page", Path(__file__).with_name("test_build_poverty_page.py"))


@pytest.fixture(scope="module")
def payload() -> dict[str, Any]:
    """The fixture payload, nudged into the shape the prose is written for (the real results
    of 1 November 2026); the invented numbers stay invented."""
    p = pages.fixture_payload()
    est = p["estimates"]
    p["derived"]["verdict"] = "higher"
    est["primary"].update(estimate=0.10, ci_low=0.05, ci_high=0.15)
    est["s5_unasked_severe"]["estimate"] = 0.04
    for e in ("s1_score", "s2_broad", "s3_head"):
        est[e]["supported"] = True
    est["ghs_dlog_consumption"].update(ci_low=-0.05, ci_high=0.1)
    est["ghs_dwork"].update(estimate=-0.2, ci_low=-0.3, ci_high=-0.1)
    est["s6_routing_free"].update(ci_low=0.0, ci_high=0.3)
    est["s2_broad"].update(estimate=0.06, ci_low=0.01, ci_high=0.5)
    for k in ("s4_education", "s4_living_standards"):
        est[k].update(ci_low=-0.01, ci_high=0.01)
    mpi, ghs = p["summary"]["mpi"], p["summary"]["ghs"]
    ghs["attrition_age_attriters"]["value"] = 30.0
    ghs["attrition_age_stayers"]["value"] = 40.0
    ghs["attrition_severe_w4_attriters"]["value"] = 0.03
    ghs["attrition_severe_w4_stayers"]["value"] = 0.02
    mpi["propensity_chosen"]["value_text"] = "logistic"
    mpi["propensity_lowest"]["value_text"] = "forest"
    for k, v in (("missing_poor_households", 40.0), ("missing_exposure_primary_households", 35.0)):
        mpi[k].update(value=v, suppressed=False)
    return p


def test_guard_names_the_claim_that_became_false(payload: dict[str, Any]) -> None:
    changed = copy.deepcopy(payload)
    changed["estimates"]["x1_sector_urban"]["estimate"] = -1.0
    with pytest.raises(ValueError, match="urban above rural"):
        ms.build(changed)


def _built(payload: dict[str, Any]) -> str:
    return ms.build(payload)


def test_manuscript_from_fixtures(payload: dict[str, Any], tmp_path: Path) -> None:
    md = _built(payload)
    assert ms.text.forbidden(md) == []
    assert ms.body_words(md) <= ms.WORD_LIMIT
    assert ms.abstract_words(md) <= ms.ABSTRACT_LIMIT
    assert "an adjusted association, not a causal effect" in md
    out = tmp_path / "m.md"
    data = tmp_path / "poverty.json"
    data.write_text(__import__("json").dumps(payload), encoding="utf-8")
    args = ["--data", str(data), "--md", str(out)]
    assert ms.main([*args, "--check"]) == 1
    assert ms.main(args) == 0
    assert ms.main([*args, "--check"]) == 0
    out.write_text(md + "x", encoding="utf-8")
    assert ms.main([*args, "--check"]) == 1


def test_refuses_other_verdict(payload: dict[str, Any]) -> None:
    changed = copy.deepcopy(payload)
    changed["derived"]["verdict"] = "inconclusive"
    with pytest.raises(ValueError, match="verdict"):
        ms.build(changed)


def test_pval_apa() -> None:
    nums = ms.text.Numbers({"a": 0.0004, "b": 0.0126, "c": 0.5}, html_mode=False)
    assert ms.pval(nums, "a") == "p < .001"
    assert ms.pval(nums, "b") == "p = .013"
    assert ms.pval(nums, "c") == "p = .500"


def test_blind_withholds_identifying_links() -> None:
    md = (
        "See (https://osf.io/kes3p/, x) and https://github.com/batestguy/curb-cut; "
        "https://batestguy.github.io/curb-cut/poverty.html) and "
        "https://doi.org/10.5281/zenodo.24050358)."
    )
    out = ms.blind(md)
    assert "osf.io" not in out and "batestguy" not in out and "zenodo" not in out
    assert out.count(ms.WITHHELD) == 4
    with pytest.raises(ValueError):
        ms.blind("the Curb Cut project")


def test_word_count_counts_only_the_body() -> None:
    md = (
        f"## Abstract\n\none two\n\n**Keywords:** k\n\n{ms.BODY_START}\n"
        f"## Intro\n\na b c\n{ms.BODY_END}\nrefs refs"
    )
    assert ms.body_words(md) == 4  # "Intro" + a b c
    assert ms.abstract_words(md) == 2


def test_prereg_exposure_shares_are_in_the_frozen_plan() -> None:
    plan = (ROOT / "docs" / "preregistration.md").read_text(encoding="utf-8")
    item9 = re.search(r"The other definitions in the same run: [^\n]+", plan)
    assert item9, "section 2.2 item 9 not found"
    for key, share in ms.PREREG_EXPOSURE.items():
        label = {"primary": "primary", "s2": "S2", "s5": "S5", "s6": "S6"}[key]
        assert f"{label} {share}" in plan, (key, share)


def test_committed_manuscript_has_no_microdata_paths() -> None:
    md = (ROOT / "docs" / "paper" / "p5-manuscript.md").read_text(encoding="utf-8")
    assert "data/restricted" not in md


def test_table1_shows_suppressed_cells_as_suppressed() -> None:
    rows = ms.load_table1()
    table = ms.Table1(rows)
    hidden = [r for r in rows if r["suppressed"] == "True"]
    assert hidden, "the committed Table 1 has suppressed cells"
    r = hidden[0]
    assert table.shown(r["characteristic"], r["category"], r["group"]) == "suppressed"
    with pytest.raises(ValueError, match="suppressed"):
        table.value(r["characteristic"], r["category"], r["group"])
    md = ms.table1_md(table)
    assert md.startswith("**Table 1.**") and "suppressed" in md


def test_table1_guard_names_the_claim(payload: dict[str, Any]) -> None:
    rows = [dict(r) for r in ms.load_table1()]
    for r in rows:
        if r["characteristic"] == "head_sex" and r["category"] == "female":
            r["value"] = "0.5" if r["group"] == "unexposed" else "0.1"
    with pytest.raises(ValueError, match="female head"):
        ms.build(payload, rows)
