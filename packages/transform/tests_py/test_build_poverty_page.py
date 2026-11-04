"""Tests for the P5 poverty page, the brief, the poverty charts and the export's payload.

Built from the committed synthetic fixtures (``packages/transform/fixtures/aggregates/
p5_*.csv``, invented numbers in the gate's schema), loaded into an in-memory DuckDB with the
staging and mart columns. No real result is used, so the tests run in CI's python job.
"""

from __future__ import annotations

import copy
import html
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "packages" / "transform" / "scripts"
FIXTURES = ROOT / "packages" / "transform" / "fixtures" / "aggregates"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


export = _load("export_marts")
charts_mod = _load("build_charts")
page_mod = _load("build_poverty_page")
brief_mod = _load("build_brief")
text = _load("poverty_text")
dot_svg = _load("dot_svg")


def _csv(name: str) -> str:
    return f"read_csv('{(FIXTURES / name).as_posix()}', header = true, all_varchar = true)"


def fixture_payload() -> dict[str, Any]:
    """poverty.json as export_marts would write it from the fixture warehouse."""
    con = duckdb.connect()
    union = f"select * from {_csv('p5_mpi_estimates.csv')} union all select * from " + _csv(
        "p5_ghs_estimates.csv"
    )
    con.execute(
        f"""create table mart_p5_estimates as
        select estimate_id, analysis, "group" as estimate_group, label, outcome, exposure,
            scale, nullif(learners, '') as learners,
            cast(nullif(estimate, '') as double) as estimate,
            cast(nullif(se, '') as double) as se,
            cast(nullif(ci_low, '') as double) as ci_low,
            cast(nullif(ci_high, '') as double) as ci_high,
            cast(nullif(pval, '') as double) as pval,
            cast(nullif(holm_p, '') as double) as holm_p,
            case lower(supported) when 'true' then true when 'false' then false end
                as supported,
            cast(nullif(mu0, '') as double) as mu0,
            cast(n as integer) as n,
            cast(nullif(n_exposed, '') as integer) as n_exposed,
            cast(nullif(n_unexposed, '') as integer) as n_unexposed,
            lower(suppressed) = 'true' as suppressed,
            case when outcome = 'dlog_consumption' then 1 else 100 end as display_factor,
            case "group" when 'headline' then 1 when 'secondary' then 2 else 3 end
                as group_order
        from ({union})"""
    )
    union = f"select * from {_csv('p5_mpi_summary.csv')} union all select * from " + _csv(
        "p5_ghs_summary.csv"
    )
    con.execute(
        f"""create table mart_p5_summary as
        select analysis, item_id, section, label, kind,
            cast(nullif(value, '') as double) as value, nullif(value_text, '') as value_text,
            lower(suppressed) = 'true' as suppressed
        from ({union})"""
    )
    return export.poverty_payload(con)


@pytest.fixture(scope="module")
def payload() -> dict[str, Any]:
    return fixture_payload()


@pytest.fixture(scope="module")
def site_build(
    payload: dict[str, Any], tmp_path_factory: pytest.TempPathFactory
) -> tuple[str, Path]:
    """The page's HTML and the data folder it was built from (downloads in downloads/)."""
    data = tmp_path_factory.mktemp("data")
    (data / "charts").mkdir()
    (data / "poverty.json").write_text(json.dumps(payload), encoding="utf-8")
    for name, doc in charts_mod.poverty_charts(data).items():
        (data / "charts" / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    out = tmp_path_factory.mktemp("site") / "poverty.html"
    args = ["--data-dir", str(data), "--page", str(out), "--site-url", "https://x.test/cc"]
    assert page_mod.main(args) == 0
    return out.read_text(encoding="utf-8"), data


@pytest.fixture(scope="module")
def built(site_build: tuple[str, Path]) -> str:
    return site_build[0]


# --- export -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("low", "high", "verdict"),
    [
        (0.06, 0.17, "higher"),
        (0.001, 0.05, "higher"),
        (-0.17, -0.06, "lower"),
        (-0.015, 0.019, "no meaningful difference"),
        (0.002, 0.019, "no meaningful difference"),  # excludes 0 but within +/-2 points
        (-0.01, 0.05, "inconclusive"),
        (-0.03, 0.01, "inconclusive"),
    ],
)
def test_section4_verdict(low: float, high: float, verdict: str) -> None:
    assert export.section4_verdict(low, high) == verdict


def test_payload_derived_values(payload: dict[str, Any]) -> None:
    est = payload["estimates"]
    d = payload["derived"]
    assert d["verdict"] == "higher"  # fixture primary 0.1 (0.06 to 0.14)
    assert d["primary_implied"] == pytest.approx(est["primary"]["mu0"] + 0.1)
    assert d["share_inside_overlap"] == pytest.approx(0.41)
    assert d["relative_increase"] == pytest.approx(0.17)
    assert d["placebo_as_extreme"] == 0
    assert d["robustness"] == {"min": 0.11, "max": 0.11}
    assert est["x1_zone_south_west"]["suppressed"] is True
    assert est["x1_zone_south_west"]["estimate"] is None
    assert payload["summary"]["mpi"]["missing_poor_households"]["suppressed"] is True


def test_payload_refuses_a_suppressed_primary(payload: dict[str, Any]) -> None:
    con = duckdb.connect()
    con.execute("create table mart_p5_estimates as select 1 as x")
    with pytest.raises(duckdb.Error):
        export.poverty_payload(con)


# --- wording guard ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("phrase", "bad"),
    [
        ("This is an adjusted association, not a causal effect.", False),
        ("the causal effect of", True),
        ("The Effect of Disability on poverty", True),
        ("the impact of poverty", True),
        ("disability causes poverty", True),
        ("poverty caused by disability", True),
        ("an event study", True),
        ("event\n studies", True),
        ("a random common cause check, because", False),
    ],
)
def test_forbidden(phrase: str, bad: bool) -> None:
    assert bool(text.forbidden(phrase)) is bad


# --- the page -----------------------------------------------------------------------------


def _value(payload: dict[str, Any], key: str) -> Any:
    node: Any = payload
    for part in key.split("."):
        node = node[part]
    return node


def test_every_number_span_matches_the_payload(payload: dict[str, Any], built: str) -> None:
    spans = re.findall(
        r'<span class="n" data-key="([^"]+)" data-factor="([^"]+)" data-decimals="(\d+)" '
        r'data-format="(\w+)">([^<]*)</span>',
        built,
    )
    assert len(spans) > 150
    for key, factor, decimals, fmt, shown in spans:
        value = _value(payload, html.unescape(key))
        shown = html.unescape(shown)
        if fmt == "text":
            assert shown == str(value)
        elif fmt == "int":
            assert shown == f"{round(value):,}"
        elif fmt == "p":
            assert shown == ("<0.0001" if value < 0.0001 else text.fixed(value, 4))
        else:
            assert shown == text.fixed(float(factor) * value, int(decimals)), key


def test_page_structure_and_wording(payload: dict[str, Any], built: str) -> None:
    assert not text.forbidden(built)
    assert built.count('<a class="skip-link" href="#main">') == 1
    assert '<main id="main" tabindex="-1"' in built
    assert 'aria-current="page">Disability and poverty</a>' in built
    assert "<script" not in built
    plain = " ".join(html.unescape(re.sub(r"<[^>]+>", "", built)).split())
    assert (
        "People in households with a member aged 5 or older who has a severe difficulty are "
        "10.0 percentage points more likely to be multidimensionally poor than people in "
        "comparable households (95% confidence interval 6.0 to 14.0 points)." in plain
    )
    assert "An adjusted association, not a causal effect" in plain
    assert "Poverty can come first" in plain and "Some shared factors were not measured" in plain
    assert "not the Washington Group's DISABILITY3 measure" in plain
    assert "Exploratory, not confirmatory" in plain
    assert "has not yet been tested by a regular screen-reader user" in plain
    # The suppressed X1 subgroup, and the unsupported S3 in the fixtures.
    assert "not shown: too few households" in plain
    assert "under 30" in plain
    assert "2 of S1, S2 and S3 are supported" in plain
    # Every <details> has a summary, every table a caption, each caption its Tab stop.
    assert built.count("<details") == built.count("<summary>") == 4
    assert built.count('<caption tabindex="0">') == built.count("<table>")
    assert 'role="region"' not in built
    # The overlap estimate has the same box as the main one, labelled secondary.
    assert built.count('<div class="p5-result">') == 2
    assert "Secondary: households where the comparison is better supported" in plain
    # Reporting the reviewer asked for: missing counts, quantiles, the RCC allowance, S4 note.
    assert "were left out for missing poverty data" in plain
    assert "of households below" in plain
    assert "the fold split alone moves it that much" in plain
    assert "do not add exactly to S1" in plain
    assert "so it is not an upper bound" in plain
    assert "two bounds" not in plain
    assert "Values near the middle" not in plain
    assert "Of 1,200 people aged 15 and over in 2018/19, 1,000 were found again" in plain


@pytest.mark.parametrize(
    ("low", "high", "start"),
    [
        (-0.15, -0.05, "are -10.0 percentage points less likely"),
        (-0.01, 0.019, "are about as likely"),
        (-0.05, 0.2, "The survey cannot tell whether"),
    ],
)
def test_headline_follows_the_verdict(
    payload: dict[str, Any], low: float, high: float, start: str
) -> None:
    changed = copy.deepcopy(payload)
    changed["estimates"]["primary"].update(ci_low=low, ci_high=high)
    changed["estimates"]["primary"]["estimate"] = (
        -0.1 if high < 0 else changed["estimates"]["primary"]["estimate"]
    )
    changed["derived"]["verdict"] = export.section4_verdict(low, high)
    nums = text.Numbers(changed, html_mode=False)
    assert start in text.headline(nums)
    rule = text.verdict_rule(nums)
    assert "rule fixed before the analysis" in rule
    with pytest.raises(ValueError, match="higher"):
        brief_mod.brief_md(changed)


def test_page_refuses_forbidden_wording(payload: dict[str, Any], tmp_path: Path) -> None:
    changed = copy.deepcopy(payload)
    changed["estimates"]["rob_no_head_education"]["label"] = "An event study"
    data = tmp_path / "data"
    (data / "charts").mkdir(parents=True)
    (data / "poverty.json").write_text(json.dumps(changed), encoding="utf-8")
    for name, doc in charts_mod.poverty_charts(data).items():
        (data / "charts" / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    assert page_mod.main(["--data-dir", str(data), "--page", str(tmp_path / "p.html")]) == 1
    assert not (tmp_path / "p.html").exists()


def test_charts_pass_their_audits_and_use_the_payload(payload: dict[str, Any], tmp_path: Path):
    (tmp_path / "poverty.json").write_text(json.dumps(payload), encoding="utf-8")
    docs = charts_mod.poverty_charts(tmp_path)
    for doc in docs.values():
        assert doc["audit"]["passed"]
        # Neutral alt-text: every row, in table order, no ranking or difference claims.
        alt = doc["alt_text"]
        assert "Highest" not in alt and "Lowest" not in alt and "difference from" not in alt
        for name in doc["data"]["categories"]:
            assert name in alt
        assert doc["meta"]["generator"] == "disability_access_charts.plots.dot"
        assert "findings" not in doc
    head = docs["poverty_headline"]["data"]["series"][0]
    assert head["values"][0] == pytest.approx(100 * payload["estimates"]["primary"]["estimate"])
    dims = docs["poverty_dimensions"]["data"]["series"][0]
    assert min(dims["lower"]) < 0  # the fixture's education interval crosses zero
    svg = dot_svg.render_dot_svg(docs["poverty_dimensions"])
    assert 'class="dot-zero"' in svg
    changed = copy.deepcopy(payload)
    changed["estimates"]["s4_health"]["suppressed"] = True
    (tmp_path / "poverty.json").write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(SystemExit, match="suppressed"):
        charts_mod.poverty_charts(tmp_path)


def test_nice_range() -> None:
    assert dot_svg.nice_range(0.5, 17.2) == (0.0, 20.0, 5.0)
    bottom, top, step = dot_svg.nice_range(-0.5, 3.2)
    assert bottom < 0 < top and bottom % step == 0
    assert dot_svg.nice_range(-3.0, -1.0)[1] == 0.0


# --- the brief ----------------------------------------------------------------------------


def test_brief_from_fixtures(payload: dict[str, Any], tmp_path: Path) -> None:
    md = brief_mod.build(payload)
    flat = " ".join(md.split())
    assert not text.forbidden(md)
    assert md.startswith("---\ntitle:")
    assert "an adjusted association, not a causal effect" in flat
    assert "https://osf.io/abcde/" in flat
    assert "no DHS data are used in this brief" in flat
    assert "National Data Archive" in flat
    assert len(md.split()) < 1250  # about two printed pages; the PDF's page count is tested too
    data = tmp_path / "poverty.json"
    data.write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "brief.md"
    page = tmp_path / "brief.html"
    args = ["--data", str(data), "--md", str(out), "--html-out", str(page)]
    assert brief_mod.main(args) == 0
    # No HTML made from this markdown yet: the check fails.
    assert brief_mod.main([*args, "--check"]) == 1
    stamp = f"<!-- {brief_mod.SOURCE_STAMP} {brief_mod.md_sha256(md)} -->"
    page.write_text(f"<html></html>\n{stamp}\n", encoding="utf-8")
    assert brief_mod.main([*args, "--check"]) == 0
    out.write_text(md + "edited\n", encoding="utf-8")
    assert brief_mod.main([*args, "--check"]) == 1


def test_long_date() -> None:
    assert brief_mod.long_date("2026-11-01T09:28:07+00:00") == "1 November 2026"


# --- Downloads (P6 item 2) -------------------------------------------------------------------

TABLE_AND_LINE = re.compile(
    r'<table><caption tabindex="0">(.*?)</caption><thead>.*?</thead>'
    r"<tbody>(.*?)</tbody></table></div>"
    r'(<p class="table-download">.*?</p>)?',
    re.S,
)
CELL = re.compile(r"<t([hd])[^>]*>(.*?)</t[hd]>", re.S)
SPAN = re.compile(
    r'<span class="n" data-key="[^"]+" data-factor="[^"]+" data-decimals="(\d+)" '
    r'data-format="(\w+)">([^<]*)</span>'
)
LINK = re.compile(r'<a href="([^"]+)" download aria-label="([^"]+)">([^<]+)</a>')


def _plain(cell: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", cell))


def test_every_table_has_downloads_equal_to_its_rows(site_build: tuple[str, Path]) -> None:
    """All 13 tables are followed by their download line; each CSV holds the table's rows
    (numbers unrounded: each rounds to the number shown) and the JSON the same rows."""
    downloads = page_mod.downloads
    page, data = site_build
    tables = TABLE_AND_LINE.findall(page)
    assert len(tables) == page.count("<table>") == 13
    labels: list[str] = []
    for caption, body, line in tables:
        assert line, caption
        files = {}
        for href, label, shown in LINK.findall(line):
            labels.append(label)
            assert label.startswith(f"{shown}: ")
            assert href.startswith("./data/downloads/poverty/")
            content = (data / href.removeprefix("./data/")).read_bytes()
            fmt = shown.split(",")[0]
            assert shown == f"{fmt}, {downloads.size_text(len(content))}"
            files[fmt] = content
        assert sorted(files) == ["CSV", "JSON"]
        csv_rows = downloads.parse_csv(files["CSV"])
        document = json.loads(files["JSON"])
        assert document["caption"] == html.unescape(caption)
        assert document["page"] == "https://x.test/cc/poverty.html"
        assert document["terms"].startswith(downloads.COMMON_TERMS)
        assert "licen" not in document["terms"].lower()
        assert csv_rows[0] == [c["label"] for c in document["columns"]]
        assert downloads.same_rows(csv_rows[1:], document["rows"])
        rows = re.findall(r"<tr>(.*?)</tr>", body, re.S)
        assert len(csv_rows) - 1 == len(rows)
        for row, got in zip(rows, csv_rows[1:], strict=True):
            values = iter(got)
            for kind, cell in CELL.findall(row):
                spans = SPAN.findall(cell)
                if not spans or all(fmt == "text" for _, fmt, _ in spans):
                    value = next(values)
                    shown = _plain(cell)
                    if kind == "d" and value and shown != value:  # a chart table's number
                        assert shown == text.fixed(float(value), 1), (value, shown)
                    else:
                        assert value == shown
                    continue
                for decimals, fmt, shown in spans:  # one value per number, "a to b" gives two
                    value, shown = float(next(values)), html.unescape(shown)
                    if fmt == "int":
                        assert shown == f"{round(value):,}"
                    elif fmt == "p":
                        assert shown == ("<0.0001" if value < 0.0001 else text.fixed(value, 4))
                    else:
                        assert shown == text.fixed(value, int(decimals))
            assert next(values, None) is None
    assert len(labels) == len(set(labels)) == 26
    files = sorted(p.name for p in (data / "downloads" / "poverty").iterdir())
    assert len(files) == 26


def test_a_range_cell_downloads_as_two_columns(site_build: tuple[str, Path]) -> None:
    _, data = site_build
    header = page_mod.downloads.parse_csv(
        (data / "downloads" / "poverty" / "benchmarks.csv").read_bytes()
    )[0]
    assert header == [
        "Hidden factor",
        "Estimate between, lower (percentage points)",
        "Estimate between, upper (percentage points)",
        "95% interval, lower (percentage points)",
        "95% interval, upper (percentage points)",
    ]
