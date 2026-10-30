"""Tests for scripts/build_state_pages.py and scripts/dot_svg.py.

The pages are built from a synthetic warehouse in memory: the 37 states from the committed
seeds and made-up cells with the marts' columns, including a suppressed cell, a state with no
survey data and an unreliable breakdown. No real survey figure is used, so the tests run in
CI's python job, which has no warehouse.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import duckdb
import pytest
from disability_access_charts import audit

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "packages" / "transform" / "scripts"
SEEDS = ROOT / "packages" / "transform" / "seeds"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look their module up while it loads
    spec.loader.exec_module(module)
    return module


pages = _load("build_state_pages")
dot_svg = _load("dot_svg")

NO_DATA = "Zamfara"  # no survey cells at all
# Edo: one wealth cell suppressed (under 30), one withheld (complementary), one walking cell
# suppressed, and a 5-17 cell under 0.05% and one flagged unreliable.
SUPPRESSED = "Edo"
NATIONAL = "Nigeria as a whole"


def _seed(name: str) -> list[dict[str, str]]:
    with (SEEDS / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _cell(i: int, k: int, flag: str = "reliable") -> tuple[Any, ...]:
    p = 0.01 + 0.002 * ((i * 7 + k * 3) % 11)
    return (p, p * 0.7, p * 1.4, flag, None, False)


PRIMARY = (None, None, None, "suppressed", "n<30 (disclosure)", True)
SECONDARY = (None, None, None, "suppressed", "complementary suppression (disclosure)", True)
TINY = (0.0003, 0.0, 0.002, "review", "low_events<10", False)  # 0.03%: shown as "<0.1"
CELL_COLUMNS = (
    "estimate double, ci_low double, ci_high double, precision_flag varchar, "
    "precision_reason varchar, suppressed boolean"
)


@pytest.fixture(scope="module")
def warehouse() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    dims = _seed("dim_states.csv")
    facts = {r["state"]: r for r in _seed("state_facts.csv")}
    con.execute(
        "create table mart_state_profile (state varchar, state_code varchar, zone varchar, "
        "capital varchar, population_2023 bigint, jonapwd_total bigint)"
    )
    con.executemany(
        "insert into mart_state_profile values (?, ?, ?, ?, ?, ?)",
        [
            (
                d["state"],
                d["state_code"],
                d["zone"],
                facts[d["state"]]["capital"],
                int(facts[d["state"]]["population_2023"]),
                None if d["state"] == NO_DATA else 100_000 + i,
            )
            for i, d in enumerate(dims)
        ],
    )
    con.execute(
        "create table state_population_by_sex_2023 as "
        f"select * from read_csv('{(SEEDS / 'state_population_by_sex_2023.csv').as_posix()}')"
    )
    con.execute(
        "create table mart_prevalence_state (state_code varchar, source varchar, "
        f"measure varchar, age_group varchar, sex varchar, {CELL_COLUMNS}, has_data boolean)"
    )
    rows = []
    measures = ["disability3", *(m for m, _ in pages.DOMAINS)]
    for i, d in enumerate(dims):
        has = d["state"] != NO_DATA
        for k, measure in enumerate(measures):
            for age, sex, _ in pages.GROUPS:
                if measure != "disability3" and sex != "all":
                    continue
                cell = _cell(i, k, "review" if age == "5-17" else "reliable")
                if d["state"] == SUPPRESSED and measure == "walking_3plus":
                    cell = PRIMARY
                if d["state"] == SUPPRESSED and measure == "disability3" and age == "5-17":
                    cell = TINY if sex == "female" else _cell(i, k, "unreliable")
                rows.append((d["state_code"], "dhs2024", measure, age, sex, *cell, has))
        rows.append(
            (d["state_code"], "mpi2021", "mpi_screener_seeing_any", "18+", "all", *_cell(i, 9), has)
        )
    con.executemany(f"insert into mart_prevalence_state values ({', '.join('?' * 12)})", rows)
    con.execute(
        "create table mart_prevalence_national_zone (geography_level varchar, source varchar, "
        f"measure varchar, age_group varchar, sex varchar, {CELL_COLUMNS})"
    )
    con.executemany(
        "insert into mart_prevalence_national_zone values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [("national", "dhs2024", m, "18+", "all", *_cell(40, k)) for k, m in enumerate(measures)],
    )
    con.execute(
        "create table mart_prevalence_breakdowns (geography_level varchar, geography varchar, "
        "source varchar, measure varchar, sex varchar, breakdown varchar, "
        f"breakdown_level varchar, age_group varchar, {CELL_COLUMNS})"
    )
    rows = []
    for i, d in enumerate(dims):
        for k, (level, _) in enumerate(pages.WEALTH):
            cell = _cell(i, k)
            if d["state"] == SUPPRESSED and level == "lowest":
                cell = PRIMARY
            if d["state"] == SUPPRESSED and level == "second":
                cell = SECONDARY
            rows.append(("state", d["state_code"], "wealth_quintile", level, *cell))
        for k, (level, _) in enumerate(pages.SECTORS):
            rows.append(("state", d["state_code"], "sector", level, *_cell(i, k, "unreliable")))
    for zone in {d["zone"] for d in dims}:
        for k, (level, _) in enumerate(pages.WEALTH):
            rows.append(("zone", zone, "wealth_quintile", level, *_cell(50, k)))
    con.executemany(
        "insert into mart_prevalence_breakdowns values "
        "(?, ?, 'dhs2024', 'disability3', 'all', ?, ?, '18+', ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return con


@pytest.fixture(scope="module")
def built(warehouse: duckdb.DuckDBPyConnection, tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("site")
    geo = pages.locator_geo()
    result = pages.build(
        pages.load(warehouse), geo, out / "states", out / "charts", "https://x.test/cc"
    )
    return out, result


def test_all_37_pages_and_the_index_build(built) -> None:
    out, result = built
    assert len(result) == 37
    files = sorted(p.name for p in (out / "states").glob("*.html"))
    assert len(files) == 38 and "index.html" in files
    index = (out / "states" / "index.html").read_text(encoding="utf-8")
    assert len(re.findall(r'<li><a href="\./[a-z-]+\.html">', index)) == 37
    share = json.loads((out / "states" / "share-images.json").read_text(encoding="utf-8"))
    assert [s["slug"] for s in share] == [p.slug for p in result]


def test_slugs_are_unique_and_stable() -> None:
    names = [r["state"] for r in _seed("dim_states.csv")]
    slugs = [pages.state_slug(n) for n in names]
    assert len(set(slugs)) == 37
    assert all(re.fullmatch(r"[a-z]+(-[a-z]+)*", s) for s in slugs)
    assert pages.state_slug("Akwa Ibom") == "akwa-ibom"
    assert pages.state_slug("Cross River") == "cross-river"
    assert pages.state_slug("Federal Capital Territory") == "federal-capital-territory"


def test_every_chart_document_audits_clean(built) -> None:
    out, _ = built
    docs = sorted((out / "charts").glob("*.json"))
    assert len(docs) == 36  # the state with no data has no chart
    for path in docs:
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["audit"]["passed"], path.name
        assert audit(doc)["passed"], path.name  # re-audited from the written file
        assert doc["findings"]["lines"]["count"]


def test_suppressed_cells_render_as_not_shown(built) -> None:
    out, _ = built
    html = (out / "states" / "edo.html").read_text(encoding="utf-8")
    assert html.count(f'<td colspan="4">{pages.TOO_FEW}</td>') == 1
    assert html.count(f'<td colspan="4">{pages.esc(pages.WITHHELD)}</td>') == 1
    # Unreliable cells are not shown anywhere, children's included; review cells are hedged.
    assert '<th scope="row">Children 5\u201317</th><td colspan="4">' in html
    # An estimate above 0 that would round to 0.0 reads "<0.1", its interval kept.
    assert (
        '<th scope="row">Girls 5\u201317</th><td class="num">&lt;0.1</td>'
        '<td class="num">0.0</td><td class="num">0.2</td>'
    ) in html
    # The suppressed activity is left out of the chart and named as withheld.
    doc = json.loads((out / "charts" / "edo.json").read_text(encoding="utf-8"))
    assert "Walking or climbing steps" not in doc["data"]["categories"]
    assert doc["findings"]["withheld"] == ["Walking or climbing steps"]


def test_unreliable_breakdowns_are_not_shown(built) -> None:
    out, _ = built
    html = (out / "states" / "kano.html").read_text(encoding="utf-8")
    assert html.count(pages.TOO_IMPRECISE) == 2  # urban and rural, flagged unreliable here


def test_a_state_with_no_data_still_gets_a_page(built) -> None:
    out, _ = built
    html = (out / "states" / "zamfara.html").read_text(encoding="utf-8")
    assert "No DHS 2024 disability figure for adults is published for Zamfara." in html
    assert "The activity chart is not shown" in html
    assert "JONAPWD publishes no figure for Zamfara." in html


def test_page_shape_and_share_tags(built) -> None:
    _, result = built
    page = next(p for p in result if p.slug == "federal-capital-territory")
    html = page.html
    assert '<html lang="en-NG">' in html
    assert "<title>Disability in the Federal Capital Territory: Curb Cut</title>" in html
    assert "<h1>Disability in the Federal Capital Territory</h1>" in html
    assert "<script" not in html
    assert len(html.encode("utf-8")) < 60 * 1024
    assert 'content="https://x.test/cc/states/federal-capital-territory.html"' in html
    assert 'content="https://x.test/cc/share/federal-capital-territory.png"' in html
    alt = re.search(r'og:image:alt" content="([^"]*)"', html)
    assert alt and alt.group(1) == page.sentence.replace("'", "&#x27;")
    assert page.sentence.startswith("In the Federal Capital Territory, the DHS 2024 survey")
    assert "has automated accessibility tests (axe, keyboard)" in html
    assert "has not yet been tested\nby a regular screen-reader user" in html
    assert "checked by keyboard" not in html
    # Every table is a focusable, named region, so a table that scrolls is reachable.
    wraps = re.findall(r'<div class="table-wrap"[^>]*>', html)
    assert wraps and all('role="region" tabindex="0" aria-label="' in w for w in wraps)
    assert not re.search(r"\bthe first\b|\bfirst[\s-]+ever\b", html, re.I)
    for table in re.findall(r"<table>.*?</table>", html, re.S):
        assert "<caption>" in table
        assert not re.search(r"<th(?=[\s>])(?![^>]*scope=)", table)


def test_the_build_refuses_a_failed_audit(warehouse, tmp_path, monkeypatch) -> None:
    real = pages.dot

    def failing(*args, **kwargs):
        doc = real(*args, **kwargs)
        doc["audit"] = {**doc["audit"], "passed": False}
        return doc

    monkeypatch.setattr(pages, "dot", failing)
    with pytest.raises(ValueError, match="chart audit failed"):
        pages.build(pages.load(warehouse), pages.locator_geo(), tmp_path, tmp_path, "https://x/")


def test_main_writes_from_a_warehouse_file(warehouse, tmp_path) -> None:
    db = tmp_path / "w.duckdb"
    warehouse.execute(f"attach '{db.as_posix()}' as w")
    for table in [r[0] for r in warehouse.execute("show tables").fetchall()]:
        warehouse.execute(f"create table w.{table} as select * from memory.{table}")
    warehouse.execute("detach w")
    args = [
        "--db",
        str(db),
        "--pages-dir",
        str(tmp_path / "p"),
        "--charts-dir",
        str(tmp_path / "c"),
    ]
    assert pages.main(args) == 0
    assert len(list((tmp_path / "p").glob("*.html"))) == 38


def test_main_fails_without_37_states(tmp_path) -> None:
    db = tmp_path / "empty.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute(
            "create table mart_state_profile as select 'A' as state, 'NG-A' as state_code, "
            "'Z' as zone, 'C' as capital, 1 as population_2023, 1 as jonapwd_total"
        )
    assert pages.main(["--db", str(db), "--pages-dir", str(tmp_path / "p")]) == 1


# --- dot_svg ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def doc(built) -> dict:
    out, _ = built
    return json.loads((out / "charts" / "kano.json").read_text(encoding="utf-8"))


def test_svg_draws_every_value_with_its_interval_and_label(doc: dict) -> None:
    svg = dot_svg.render_dot_svg(doc)
    assert svg.startswith('<svg class="dot-svg"') and 'aria-hidden="true"' in svg
    data = doc["data"]
    n = len(data["categories"]) * len(data["series"])
    assert svg.count("dot-mark") == n
    assert svg.count("dot-whisker") == n
    labels = re.findall(r'class="dot-text dot-value"[^>]*>([^<]*)<', svg)
    expected = [
        f"{s['values'][i]:.1f}%" for i in range(len(data["categories"])) for s in data["series"]
    ]
    assert labels == expected
    for category in data["categories"]:
        assert f">{category}</text>" in svg
    # Colours are never written in: they come from the page's CSS custom properties.
    assert "#" not in re.sub(r"&#x?[0-9a-f]+;", "", svg)


def test_svg_positions_follow_the_values(doc: dict) -> None:
    svg = dot_svg.render_dot_svg(doc)
    xs = [float(x) for x in re.findall(r'<circle class="dot-s0 dot-mark" cx="([\d.]+)"', svg)]
    values = doc["data"]["series"][0]["values"]
    top, _ = dot_svg.nice_max(max(v for s in doc["data"]["series"] for v in s["upper"]))
    for x, v in zip(xs, values, strict=True):
        want = dot_svg.PLOT_LEFT + (dot_svg.PLOT_RIGHT - dot_svg.PLOT_LEFT) * v / top
        assert abs(x - want) < 0.06


def test_theme_css_uses_the_document_themes(doc: dict) -> None:
    css = dot_svg.theme_css(doc)
    light, dark = doc["themes"]["light"], doc["themes"]["dark"]
    assert f"--dot-s0:{light['series'][0]}" in css
    assert f"@media (prefers-color-scheme: dark){{.dot-chart{{--dot-s0:{dark['series'][0]}" in css
    assert f"--dot-text:{dark['text']}" in css
    only_light = {**doc, "themes": {"light": light}}
    assert "@media" not in dot_svg.theme_css(only_light)


def test_the_state_chart_compares_the_state_alone(doc: dict) -> None:
    assert [s["name"] for s in doc["data"]["series"]] == ["Kano"]
    named = {c[k]["series"] for c in doc["findings"]["comparisons"] for k in ("a", "b")}
    assert named == {"Kano"}
    assert NATIONAL not in doc["alt_text"]


def test_a_value_under_0_05_is_labelled_under_0_1() -> None:
    assert dot_svg.label_text(0.03, 1) == "<0.1"
    assert dot_svg.label_text(0.0, 1) == "0.0"
    assert dot_svg.label_text(0.05, 1) == "0.1"
    assert pages.num1(0.03) == "<0.1" and pages.num1(0.0) == "0.0"


def test_legend_shows_each_series_with_its_shape(doc: dict) -> None:
    trace = doc["plotly"]["data"][0]
    two = {
        **doc,
        "data": {**doc["data"], "series": doc["data"]["series"] * 2},
        "plotly": {"data": [trace, {**trace, "marker": {**trace["marker"], "symbol": "diamond"}}]},
    }
    legend = dot_svg.legend_html(two)
    assert legend.count("<li>") == 2 and "<circle" in legend and "<path" in legend
    assert dot_svg.legend_html(doc) == ""


@pytest.mark.parametrize("symbol", ["circle", "diamond", "square", "triangle-up", "x", "star", "?"])
def test_every_marker_shape_draws(symbol: str) -> None:
    out = dot_svg.marker(symbol, 10, 10, "dot-s0 dot-mark")
    assert out.startswith(("<circle", "<rect", "<path")) and 'class="dot-s0 dot-mark"' in out


@pytest.mark.parametrize(
    ("value", "top", "step"),
    [(0.0, 1.0, 0.25), (2.9, 3.0, 1.0), (14.1, 15.0, 5.0), (0.37, 0.4, 0.1), (100, 100, 25)],
)
def test_nice_max(value: float, top: float, step: float) -> None:
    assert dot_svg.nice_max(value) == pytest.approx((top, step))


def test_an_empty_chart_is_refused(doc: dict) -> None:
    with pytest.raises(ValueError, match="at least one category"):
        dot_svg.render_dot_svg({**doc, "data": {**doc["data"], "categories": []}})


def test_the_build_refuses_a_page_over_budget(warehouse, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pages, "HTML_BUDGET", 1000)
    with pytest.raises(ValueError, match="page budget"):
        pages.build(pages.load(warehouse), pages.locator_geo(), tmp_path, tmp_path, "https://x/")
