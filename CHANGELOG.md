# Changelog

All notable changes to this project are documented here. Entries follow [Conventional Commits](https://www.conventionalcommits.org/).

## [Unreleased]

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
