# Changelog

All notable changes to this project are documented here. Entries follow [Conventional Commits](https://www.conventionalcommits.org/).

## P3 — in progress (2026-10-24)

### Added
- feat(ingest): restricted-zone harmonisers for Nigeria DHS 2024, NBS MPI 2021 and GHS-Panel W4/W5 (person-level Parquet, local only); MPI is kept on its own non-WG definitions and never reported as DISABILITY3 (`verification.md` D39, D43).
- feat(ingest): survey estimation in R (`survey`, Korn–Graubard intervals with design df), one disclosure gate (cells under 30 unweighted respondents suppressed), an NCHS precision flag plus a 10-event rule, and a provenance manifest.
- feat(data): first public aggregates: DHS 2024 by state (18+ and 5–17) and nationally, GHS W4/W5 nationally and by zone. MPI aggregates are built but held until the NBS reply / P4 gate.
- feat(transform): metaplane `dbt_expectations`, prevalence marts, a synthetic fixtures target run in CI, disclosure and scope tests, `dbt docs` artifact; WorldPop v3.0 state totals (CC BY 4.0) and the NBS Annex 3 state × sex seed.
- docs: `docs/reproduce.md`; JONAPWD extraction accuracy (80/80 sampled cells).

### Changed
- docs: DHS 2024 is the main prevalence source (MPI's seeing, hearing and walking severity was asked only of aid users); GHS W3 dropped.

## P2 — 2026-10-22 (disability-access-charts 0.1.0 on PyPI)

### Added
- feat(charts): `disability-access-charts` 0.1.0, "charts that check their own words":
  - `bar()` and `dot()` (with optional confidence intervals) build one JSON chart document: Plotly spec, themes, data-derived alt-text, table, `data` and `keyboard` blocks, audit and provenance;
  - dot plots set series side by side (`scattermode: "group"`) with whiskers in each series' colour, so intervals neither overlap nor lose their dot;
  - a claim checker in `describe.py`: every number must belong to the nearest category in its part of the clause, with chart-wide counts and totals read only after their cue words; extremes, pairwise comparisons (lists of names checked pair by pair), ratios (±5%), ranks (digits and words, "second-highest", "number one") and equality are checked against the data; with intervals, comparisons must pass a difference test (1.96·√(se_a²+se_b²)) and an unqualified superlative must be separated from every other group; "no difference" always fails; negated, qualified and contrasted claims, unlisted comparatives, spelled-out numbers and clauses naming two groups without a recognised claim give "unchecked" warnings. a second comparison after "and" or "but" reuses the first subject, and a part starting with a verb ("and is the highest") is about the clause's first names; numbers attach to the preceding name, to the name in "N% in Name", or pair in order under "respectively", "X to Y" must be a name's (lower, upper), and spelled counts before the label are checked. A pass means no recognised claim was found false, not that the text is true;
  - generated alt-text with uncertainty wording ("highest estimate", the interval, whether the survey can show a difference), held to its own checker;
  - language-ready templates and claim vocabulary (`_lang/en.py`, `lang="en"`, glossary hook, `meta.alt_text_lang`); only English ships. Names that collide with checker words ("Highest", "Total") are refused;
  - `audit()` for chart documents and plain Plotly figures (contrast, alt-text, hover-only data, zoom, marker shapes, keyboard metadata, `chart-matches-data` between the `data` block, the Plotly traces and the table, warnings for a missing `data` block, vacuous alt-text and zero-width intervals), `theme()`, `to_html()` / `to_csv()`, `figure()` (optional `[plotly]` extra). The `alt-text-matches-data` check's description now reads "No number or recognised claim in the alt-text contradicts the data";
  - optional LLM polish (Gemini, then Groq), kept only when the checker finds no errors and no unchecked wording and every fact of the data-built text survives; it requires `disclosure_checked=True`, sends only the `data` block, title, source and alt-text, and caches outputs;
  - `disability-access-charts check` CLI (and `python -m disability_access_charts`), Okabe–Ito series colours checked at 3:1 per theme, three examples (the JONAPWD one labelled as assumed figures), and a README comparing it with a11yviz and maidr.
- Nigerian visual identity: flag-green brand colour (WCAG 2.2 AA in light and dark), a decorative green-white-green band and a striped SVG favicon.
- `disability_access_charts.experimental`: optional `Theme.highlight` colour, audited at 3:1 against the background and the bars (SC 1.4.11); default themes now flag green.
- "All types, by state" chart (37 bars) built with `bar_chart`; the state chosen in the explorer is highlighted with colour, outline and bold label.
- State card after "Show figures": capital, zone, 2023 population (NBS), slogan where two sources agree, JONAPWD total with share and rank, sources, and a locator map.
- dbt seed `state_facts` and mart `mart_state_profile` (exported into `states.json`), with tests.
- geoBoundaries NGA ADM1 (CC BY 4.0) committed under `data/public/geoboundaries/`; `build_map.py` builds the locator map's SVG paths in CI and fails if a state is missing.

### Changed
- test(site): Playwright previews on port 4317 (or `PREVIEW_PORT`) with `--strictPort`, so it never tests another app on vite's default port.
- refactor(site): `build_charts.py` uses `disability_access_charts.bar`; the chart files only gain fields (`data`, `keyboard`, theme `series`, more `meta`). `chart.js` colours dot-plot series and their whiskers from the theme (bar whiskers keep the text colour); `format.js` adds a `number` column type.
- Focus moves to the state card's heading after "Show figures"; the map gives up after 10 s, so the card still shows without it.

### Deprecated
- `disability_access_charts.experimental`: now thin wrappers over the 0.1 API that issue a `DeprecationWarning`.

## P1 — 2026-10-17

### Added
- JONAPWD state × disability-type extraction from the PDF text layer (`packages/ingest`), validated against rendered pages.
- dbt project (`packages/transform`): staging model, national and state marts, `dim_states` and alias seeds, 51 tests.
- `disability_access_charts.experimental.bar_chart`: Plotly spec, data-checked alt-text, table and contrast audit.
- Accessible static site with DuckDB-WASM state explorer, deployed to GitHub Pages; Playwright + axe in CI.

## P0 — 2026-10-16

### Added
- Project plan (`PLAN.md`) and verification log (`docs/verification.md`).
- uv workspace with ruff, pyright and pytest; renv; pre-commit with a restricted-data guard; CI workflow.
- `disability-access-charts` 0.0.1: WCAG 2.2 contrast checks (SC 1.4.3, 1.4.11), published via trusted publishing on `charts-v*` tags.
