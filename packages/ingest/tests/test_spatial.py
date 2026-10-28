"""Spatial analysis: the spec, and checks on the committed outputs in data/public/spatial/.

R is not run in CI; these tests read the committed files.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from curbcut_ingest.spatial import DOMAINS, K_RANGE, KNOWN_PAIRS, NSIM, OUT, moran_measures, spec
from curbcut_ingest.states import StateLookup

CODES = {s.state_code for s in StateLookup.from_seeds().states.values()}


def _rows(name: str) -> list[dict[str, str]]:
    with (OUT / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_spec_measures() -> None:
    measures = moran_measures()
    assert len(measures) == 8
    assert (measures[0]["measure"], measures[0]["age_group"]) == ("disability3", "18+")
    assert [m["measure"] for m in measures[1:7]] == list(DOMAINS)
    assert (measures[-1]["measure"], measures[-1]["age_group"], measures[-1]["role"]) == (
        "disability3",
        "5-17",
        "secondary",
    )
    s = spec(Path("out"))
    assert s["nsim"] == 9999
    assert s["outcome_csv"].endswith("aggregates/dhs2024_state.csv")  # type: ignore[union-attr]
    assert "jonapwd" not in json.dumps(s).lower()  # never on JONAPWD (D17)


def test_neighbours_symmetric_and_complete() -> None:
    rows = _rows("neighbours.csv")
    edges = {(r["geography"], r["neighbour"]) for r in rows}
    assert {a for a, _ in edges} == CODES
    assert all((b, a) in edges for a, b in edges)
    for a, b in KNOWN_PAIRS:
        assert (a, b) in edges
    totals: dict[str, float] = {}
    for r in rows:
        totals[r["geography"]] = totals.get(r["geography"], 0.0) + float(r["weight"])
    assert all(t == pytest.approx(1.0) for t in totals.values())  # row-standardised


def test_moran_global() -> None:
    rows = _rows("moran_global.csv")
    assert len(rows) == 8
    for r in rows:
        assert int(r["n_states"]) == 37
        assert int(r["nsim"]) == NSIM
        assert int(r["n_reliable"]) + int(r["n_review"]) + int(r["n_unreliable"]) == 37
        assert 0 < float(r["p_perm"]) <= 1
        assert float(r["p_perm"]) <= float(r["p_bh"]) <= 1


def test_lisa() -> None:
    rows = _rows("lisa_disability3_18plus.csv")
    assert {r["geography"] for r in rows} == CODES
    classes = {"High-High", "Low-Low", "High-Low", "Low-High", "Not significant"}
    for r in rows:
        assert r["lisa_class"] in classes
        assert r["exploratory"] == "TRUE"
        assert (r["lisa_class"] != "Not significant") == (float(r["q_bh"]) < 0.05)


def test_profile_clusters() -> None:
    rows = _rows("profile_clusters.csv")
    assert {r["geography"] for r in rows} == CODES
    sil = _rows("profile_silhouette.csv")
    assert [int(r["k"]) for r in sil] == list(range(K_RANGE[0], K_RANGE[1] + 1))
    chosen = [r for r in sil if r["chosen"] == "TRUE"]
    assert len(chosen) == 1
    best = max(float(r["mean_silhouette"]) for r in sil)
    assert float(chosen[0]["mean_silhouette"]) == best
    assert len({r["cluster"] for r in rows}) == int(chosen[0]["k"])


def test_summary_and_services() -> None:
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    assert len(summary["moran"]["results"]) == 8
    assert all(r["sentence"] for r in summary["moran"]["results"])
    assert summary["lisa"]["exploratory"] is True
    assert sum(summary["lisa"]["classes"].values()) == 37
    assert summary["lisa"]["sentence"].startswith("Exploratory")
    assert summary["clusters"]["sentence"].startswith("Descriptive only")
    services = json.loads((OUT / "services_vs_need.json").read_text(encoding="utf-8"))
    assert services["n_states"] == 37
    assert -1 <= services["spearman_rho"] <= 1
    assert summary["services"]["sentence"].startswith("Ecological")
