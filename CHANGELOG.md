# Changelog

All notable changes to this project are documented here. Entries follow [Conventional Commits](https://www.conventionalcommits.org/).

## [Unreleased]

### Added
- Nigerian visual identity: flag-green brand colour (WCAG 2.2 AA in light and dark), a decorative green-white-green band and a striped SVG favicon.
- `disability_access_charts.experimental`: optional `Theme.highlight` colour, audited at 3:1 against the background and the bars (SC 1.4.11); default themes now flag green.
- "All types, by state" chart (37 bars) built with `bar_chart`; the state chosen in the explorer is highlighted with colour, outline and bold label.
- State card after "Show figures": capital, zone, 2023 population (NBS), slogan where two sources agree, JONAPWD total with share and rank, sources, and a locator map.
- dbt seed `state_facts` and mart `mart_state_profile` (exported into `states.json`), with tests.
- geoBoundaries NGA ADM1 (CC BY 4.0) committed under `data/public/geoboundaries/`; `build_map.py` builds the locator map's SVG paths in CI and fails if a state is missing.

### Changed
- Focus moves to the state card's heading after "Show figures"; the map gives up after 10 s, so the card still shows without it.

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
