"""The disclosure gate and manifest, on invented cell estimates."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from curbcut_ingest import disclosure

DATASET = disclosure.Dataset(
    source="testsurvey",
    version="v1",
    title="Test survey",
    citation="Invented",
    terms="Invented terms",
    design="Invented design",
)
HELD = disclosure.Dataset(
    source="heldsurvey",
    version="v2",
    title="Held survey",
    citation="Invented",
    terms="Invented terms",
    design="Invented design",
    held=True,
    held_reason="waiting for permission",
)


def _cell(geo: str, n: int, p: float = 0.1, events: int | None = None, **over) -> dict:
    row = {
        "measure": "disability3",
        "geography_level": "state",
        "geography": geo,
        "age_group": "18+",
        "sex": "all",
        "breakdown": "all",
        "breakdown_level": "all",
        "estimate": p,
        "se": 0.01,
        "ci_low": p - 0.02,
        "ci_high": p + 0.02,
        "n_unweighted": n,
        "n_events": round(p * n) if events is None else events,
        "n_effective": n / 2,
        "df": 20,
    }
    row.update(over)
    return row


RAW = pd.DataFrame(
    [
        _cell("NG-AB", 1000),
        _cell("NG-AD", 29),  # under the threshold: suppressed
        _cell("NG-AK", 30),  # exactly the threshold: kept
        _cell("NG-AN", 800, p=0.0, events=0, ci_low=0.0, ci_high=0.004),
    ]
)


def test_gate_suppresses_small_cells() -> None:
    out = disclosure.gate(RAW, DATASET)
    assert list(out.columns) == list(disclosure.PUBLIC_COLUMNS)
    assert "n_events" not in out.columns
    # NG-AD is under 30; the four states add up to Nigeria, so the smallest other state
    # (NG-AK, exactly 30) is suppressed too, or NG-AD could be recovered by subtraction.
    assert out["suppressed"].tolist() == [False, True, True, False]
    for i in (1, 2):
        for column in (*disclosure.NULLED, "n_unweighted"):
            assert pd.isna(out.iloc[i][column])
        assert out.iloc[i]["precision_flag"] == disclosure.SUPPRESSED
    assert out.iloc[1]["precision_reason"] == "n<30 (disclosure)"
    assert out.iloc[2]["precision_reason"] == disclosure.SECONDARY_REASON
    assert out["precision_flag"].tolist() == ["reliable", "suppressed", "suppressed", "review"]
    assert out.iloc[3]["precision_reason"] == "zero_events"
    assert set(out["source"]) == {"testsurvey"}


def test_gate_keeps_a_cell_at_exactly_the_threshold() -> None:
    out = disclosure.gate(RAW.iloc[[0, 2, 3]], DATASET)
    assert out["suppressed"].tolist() == [False, False, False]
    assert out.iloc[1]["n_unweighted"] == 30
    assert out.iloc[1]["precision_reason"] == "n_effective<30"  # 30 respondents, n_eff 15


def _suppressed(cells: list[dict], zone_of: dict[str, str] | None = None) -> list[bool]:
    return disclosure.complementary(pd.DataFrame(cells), zone_of).tolist()


def test_complementary_breakdown_levels_pick_the_smallest_sibling() -> None:
    quintiles = [
        _cell("NG-AB", n, breakdown="wealth_quintile", breakdown_level=level)
        for level, n in [("lowest", 7), ("second", 78), ("middle", 420), ("fourth", 721)]
    ]
    assert _suppressed([_cell("NG-AB", 1226), *quintiles]) == [False, True, True, False, False]


def test_complementary_sex_and_two_hidden_cells_need_nothing_more() -> None:
    cells = [
        _cell("NG-AB", 25, sex="female"),
        _cell("NG-AB", 40, sex="male"),
        _cell("NG-AD", 20, sex="female"),
        _cell("NG-AD", 10, sex="male"),
    ]
    # NG-AB: one hidden among two -> male hidden too. NG-AD: both already hidden. Then the
    # states partition for each sex holds two hidden cells, which is safe.
    assert _suppressed(cells) == [True, True, True, True]


def test_complementary_cascades_across_states_zones_and_files() -> None:
    zone_of = {"NG-AB": "South East", "NG-AN": "South East", "NG-KN": "North West"}
    cells = [
        _cell("NG-AB", 20, breakdown="sector", breakdown_level="rural"),
        _cell("NG-AB", 500, breakdown="sector", breakdown_level="urban"),
        _cell("NG-AN", 300, breakdown="sector", breakdown_level="rural"),
        _cell("NG-AN", 900, breakdown="sector", breakdown_level="urban"),
        _cell("NG-KN", 600, breakdown="sector", breakdown_level="rural"),
        _cell("NG-KN", 800, breakdown="sector", breakdown_level="urban"),
    ]
    hidden = _suppressed(cells, zone_of)
    # AB rural primary -> AB urban (sector partition) -> another state in each sector
    # partition across states, chained until every partition holds 0 or 2+ hidden cells.
    assert hidden[0] and hidden[1]
    rural = [hidden[i] for i in (0, 2, 4)]
    urban = [hidden[i] for i in (1, 3, 5)]
    south_east_rural = [hidden[i] for i in (0, 2)]
    assert sum(rural) != 1 and sum(urban) != 1 and sum(south_east_rural) != 1


def test_complementary_severity_levels_sum_to_one() -> None:
    cells = [
        _cell("NG", n, geography_level="national", measure=f"seeing_level_{k}")
        for k, n in [(1, 900), (2, 500), (3, 40), (4, 12)]
    ]
    assert _suppressed(cells) == [False, False, True, True]


def test_complementary_lone_suppressed_cell_without_siblings_is_left_alone() -> None:
    cells = [
        _cell("NG", 300, geography_level="national"),
        _cell("North West", 12, geography_level="zone"),
    ]
    assert _suppressed(cells) == [False, True]


def test_gate_downgrades_low_event_cells() -> None:
    raw = pd.DataFrame(
        [
            _cell("NG-KN", 2000, p=0.004, events=8, ci_low=0.002, ci_high=0.008),
            _cell("NG-LA", 2000, p=0.005, events=10, ci_low=0.003, ci_high=0.009),
        ]
    )
    out = disclosure.gate(raw, DATASET)
    assert out["precision_flag"].tolist() == ["review", "reliable"]
    assert out["precision_reason"].tolist()[0] == "low_events<10"
    assert "n_events" not in out.columns


def test_gate_rejects_bad_input() -> None:
    with pytest.raises(disclosure.GateError):
        disclosure.gate(RAW.drop(columns=["n_events"]), DATASET)
    with pytest.raises(disclosure.GateError):
        disclosure.gate(
            RAW.assign(n_unweighted=pd.Series([1000, None, 30, 800], dtype="Float64")), DATASET
        )


def test_publish_writes_file_and_manifest(tmp_path: Path) -> None:
    path, entry = disclosure.publish(RAW, DATASET, "test.csv", tmp_path)
    assert path == tmp_path / "test.csv"
    text = path.read_text(encoding="utf-8")
    assert "\r" not in text
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    recorded = manifest["files"]["test.csv"]
    assert recorded["sha256"] == disclosure.sha256(path)
    assert recorded["suppressed_cells"] == 2
    assert recorded["secondary_suppressed_cells"] == 1
    assert recorded["rows"] == 4
    assert recorded["disclosure_threshold"] == 30
    assert recorded["precision_flags"]["suppressed"] == 2
    assert recorded["script_commit"]
    assert entry == recorded
    # Publishing again replaces the entry rather than adding one.
    disclosure.publish(RAW.iloc[:1], DATASET, "test.csv", tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["test.csv"]["rows"] == 1


def test_held_source_goes_to_its_own_folder(tmp_path: Path) -> None:
    path, _ = disclosure.publish(RAW, HELD, "held.csv", tmp_path)
    assert path == tmp_path / "heldsurvey" / "held.csv"
    public = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert "heldsurvey/held.csv" not in public.get("files", {})
    held = public["held"]["heldsurvey/held.csv"]
    assert held["status"] == "held (not published)"
    assert "sha256" not in held
    local = json.loads((tmp_path / "heldsurvey" / "manifest.json").read_text(encoding="utf-8"))
    assert local["files"]["heldsurvey/held.csv"]["sha256"] == disclosure.sha256(path)


def test_script_commit_outside_git(tmp_path: Path) -> None:
    assert disclosure.script_commit(tmp_path) == "unknown"
