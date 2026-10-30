# Changelog

All notable changes to this project are documented here. Entries follow [Conventional Commits](https://www.conventionalcommits.org/).

## P4b — in progress (2026-10-29)

### Added
- feat(charts): `disability-access-charts` 0.2.0, prepared but **not yet published** (the author approves the release separately):
  - statistical findings (`findings=True` on `bar()`, `grouped_bar()`, `dot()`; `statistical_findings()`): four pre-declared families (extremes against the next, gaps between series, neighbours in the ranking, each estimate against a `Reference`), every comparison counted, Benjamini-Hochberg false discovery rate at q = 0.05 over the claim checker's difference test written as p-values, "N comparisons checked, K supported"; findings that involve a `review` estimate are hedged, those that involve an `unreliable` or `suppressed` one are dropped and counted, and left-out categories are named. The sentences pass the claim checker; the audit checks the counts, the cited cells, a full recompute, the hedging and the sentences. Method and limits in `docs/findings.md`;
  - `patterns` module: five abstract adire-inspired tiles drawn for the library (dots, rings, checks, lines, crosshatch; never nsibidi or Ukara signs, D31), a black-or-white ink rule, Plotly `marker.pattern` and SVG `<pattern>` renderers, and audit checks (one pattern and colour per series or class, ink at 3:1 against every fill in every theme, legend). `docs/patterns.md`;
  - `grouped_bar()` (patterns on by default) and `bar(patterns=True)`; dot plots keep marker shapes (Plotly has no scatter patterns, D30);
  - `choropleth()` is stable and exported. **Changed default:** `patterns=None` (auto) gives a pattern per class with five classes or fewer, and none with more (the 0.1 document, plus a `shade-alone` audit warning); `patterns=False` gives the 0.1 document; `patterns=True` with more than five classes raises;
  - `Series(precision=...)` flags, shown in the table;
  - a patterned map example;
  - **changed from 0.1:** besides the map default above, `describe(chart_type="bar")` with several series now describes grouped bars (it raised in 0.1); in the claim checker, a list of names with values separated by semicolons ("A, 1%; B, 2%; and C, 3%") is one clause, so every estimate in a list written that way (with "; and" before the last item, as the library writes it) is checked; a two-item list without the "and", or a list separated by commas, is still only partly checked; and a hedged rank ("the second-highest estimate") no longer warns. Otherwise `bar()` and `dot()` with patterns and findings off give the 0.1 document, apart from the version;
  - review fixes before release: with `findings=True` the alt-text's "can / cannot show a difference" follows the corrected `extremes` results (`verdicts` on `describe()` and `check_alt_text()`), so the two never disagree; `fdr_q` must be at most 0.05 (it was silently capped); comparisons with a zero-width interval are dropped and counted in the findings, and the claim checker never treats such a pair as separated ("the survey cannot show a difference"); without patterns, the map's shade-only warning has its own id, `shade-alone`, so `not-colour-alone` names one check; ranking findings give each estimate's rank ("the second-highest estimate"); outlier lists use semicolons and are checked item by item; only the sentences the checker reads reserve names ("Rate", "Survey" are fine); a `dependence` caveat says BH's 5% is nominal here and gives the Benjamini-Yekutieli count; the docs' examples use synthetic names.
- feat(site): the prevalence map draws each class's pattern (never under 8 px on screen, so they stay legible at 320 px), and its legend shows each pattern with its range; the state dot plot shows its findings (73 comparisons checked, 20 supported, at q = 0.05) under the chart, in plain words, rendered apart from the chart so a problem in one never takes down the other.

## P4a — 2026-10-29 (measured prevalence, map and comparison live)

### Added
- feat(ingest): DHS 2024 direct estimates by state with complementary suppression (D49); reproduction of NDHS 2024 Tables 14.1 and 14.2.x and an R `survey` vs Python `svy` cross-check (D48).
- feat(ingest): Fay-Herriot attempt with a pre-declared covariate set; no model passed its diagnostics and the gain was negligible, so direct estimates lead and the result is published (D56).
- feat(ingest): spatial analysis (Moran's I, LISA, clustering, health facilities) on the direct estimates, with hedged sentences (D58).
- feat(charts): experimental `choropleth()` map document with its own audit (boundaries and legend at 3:1; colour never the only cue).
- feat(transform): marts for the comparison and spatial results; export of DHS prevalence, comparison and spatial data for the site; `check --strict` in CI.
- feat(site): the main page leads with measured prevalence (DHS 2024, Washington Group cut-off): a map and interval chart for all 37 states, a sourced comparison of the 15% and 3% figures, spatial findings, the state's DHS figure on the state card, and a methodology page. JONAPWD's figures move below as "what was assumed".
- test: colour tokens checked against the CSS; headline figures hard-coded; a tighter Tab-stop bound.

### Verified
- P4a gate passed (author, 2026-10-29): automated tests, a scripted NVDA transcript (Guidepup) and the author's own NVDA check of the state card.

## P3 — in progress (2026-10-24)

### Added
- feat(ingest): restricted-zone harmonisers for Nigeria DHS 2024, NBS MPI 2021 and GHS-Panel W4/W5 (person-level Parquet, local only); MPI is kept on its own non-WG definitions and never reported as DISABILITY3 (`verification.md` D39, D43).
- feat(ingest): survey estimation in R (`survey`, Korn–Graubard intervals with design df), one disclosure gate (cells under 30 unweighted respondents suppressed), an NCHS precision flag plus a 10-event rule, and a provenance manifest.
- feat(data): first public aggregates: DHS 2024 by state (18+ and 5–17) and nationally, GHS W4/W5 nationally and by zone. MPI 2021 by state and nationally, under MPI's own definitions (released 2026-10-24).
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
