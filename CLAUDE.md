# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

Phase **P1** (thin vertical slice) is built and live at https://batestguy.github.io/curb-cut/ and passed a keyboard pre-check. The author deferred the NVDA part of its gate (to be done before P6 at the latest). P2 is done: `disability-access-charts` 0.1.0 is on PyPI (2026-10-22). P3 (restricted zone + warehouse) passed its gate on 2026-10-24: disclosure-gated aggregates for DHS 2024 (the main prevalence source, `docs/verification.md` D43), MPI 2021 and GHS W4/W5 are in `data/public/aggregates/`. **P4 (prevalence) was planned on 2026-10-27, split into P4a (numbers, map, comparison) and P4b (chart library 0.2, state pages); P4a step 0 (reproduce the NDHS report tables, cross-check with `svy`) passed on 2026-10-27; step 1 (direct estimates) is next.** NDHS 2024 already publishes state disability figures (`docs/verification.md` D46), so the site never claims to be first. The Nigerian identity and state card (2026-10-17, pulled forward at the author's request) are deployed (commit 119cf4e). P0 passed its gate on 2026-10-16; its evidence is in `docs/verification.md`.

- **Start with `docs/STATUS.md`:** phase states, blockers, next actions and the decisions log. Update it at the end of every working session and at each gate.
- **`PLAN.md` is the source of truth** (agreed 2026-10-16). Read the section for the current phase before starting work.
- `CurbCut.txt` is the original spec, kept for the record. Where it disagrees with `PLAN.md`, `PLAN.md` wins — many of its claims turned out wrong (see "Corrected facts").

Update this file as real commands and structure appear, and replace the "intended" items with what actually got built.

## What the project is

Curb Cut is a zero-cost, accessible data platform for Nigerian disability data, and a portfolio piece aimed at recruiters across data roles (see the recruiter-track table in `PLAN.md`). The author has lived experience with disability and assistive technology; that story is central, not decoration. The author is not a screen-reader user: their keyboard/NVDA check is a first-time-user check, and a regular screen-reader user's feedback is required before launch.

Public GitHub repo `curb-cut`, MIT. Main components:

- **`disability-access-charts`** (Python, PyPI): accessible Plotly wrapper. Palettes, contrast checks (WCAG 2.2 SC 1.4.3 / 1.4.11), `audit(fig)` that runs in CI, `theme()`, an `disability-access-charts check` CLI, **alt-text checked against the data**, and a **data-table fallback** for every chart. It must stand apart from the existing `maidr` library. Data-derived alt-text is the default; LLM polish (Gemini → Groq) is optional, number-checked, cached, and only ever sees public aggregates.
- **Ingest:** text extraction from the JONAPWD 2025 PDF (it has a text layer: per-state Power BI pages, no OCR needed), Nigeria DHS 2024 microdata (the main prevalence source, standard WG-SS), NBS MPI 2021 microdata (its own non-WG disability items; poverty), GHS-Panel W4–W5 (W3 dropped), NBS 2023 Demographic Bulletin projections, WorldPop and geoBoundaries (CC BY).
- **Warehouse:** dbt Core **1.x** on dbt-duckdb (v2 is alpha), with the metaplane fork of dbt-expectations, a state-name alias seed, and a provenance manifest.
- **Analysis:** survey-weighted state prevalence (R `survey`, cross-checked with Python `svy`), Fay-Herriot small-area estimation (`sae`/`emdi`); pre-registered DoubleML adjusted association between disability and MPI poverty with sensemakr/E-values, placebo and DoWhy refutations; an exploratory GHS onset event study (pyfixest, checked against R `did`).
- **Site:** static, semantic HTML built with Vite, on GitHub Pages. DuckDB-WASM queries Parquet files served from the Pages site. Charts render from disability-access-charts JSON produced at build time (Plotly spec, alt-text, data table, audit result). Claude writes the JS.
- **API:** FastAPI on Render Free, **optional** — the site must never depend on it.

The architectural thesis is that disability-access-charts sits under every chart. Charts must not bypass it.

## Architecture: two data zones

Licensing (NBS / World Bank / DHS) forbids republishing household-level microdata, including inside a dashboard. Only aggregates may be public.

- **Restricted zone** — `data/restricted/`, **git-ignored, local only**. Holds microdata. Scripts produce weighted aggregates, run a **disclosure check** (suppress cells with fewer than ~30 unweighted respondents), and record source, version, licence and suppression count in a manifest.
- **Public zone** — in the repo. Aggregate Parquet → dbt marts → `site/data/*.parquet`.
- **CI never touches restricted data.** It runs `dbt build` against synthetic fixtures with the same schema.

Never commit microdata, never send it to an LLM or any external service, and never write a public output that skips the disclosure check. That includes Claude's own context and every subagent's: no `head()`, row prints or value dumps of restricted files. Print only variable metadata, counts with cells under 30 shown as "<30", or aggregates that passed the disclosure check.

## Hard constraints

- **$0/month, always.** Never introduce a paid service. HF Gradio/Docker Spaces need a paid plan; static Spaces are free. Neon/Supabase are cut.
- **No committed DuckDB file.** Public data ships as Parquet inside the Pages site (1 GB site limit; git warns over 50 MiB and rejects over 100 MiB). Do not use GitHub Release assets for data: they lack CORS headers, so DuckDB-WASM can't read them. DuckDB allows one writer at a time — no concurrent writers in CI or scripts.
- **Phase order is fixed (P0–P7 in `PLAN.md`). Stop at every phase gate for the author's review.** Scope creep is the main way this project fails. After each phase, update the README hero links and add a CHANGELOG entry (conventional commits).
- **Accessibility is a requirement.** Keyboard only (Tab reaches everything, no mouse-only interactions) and screen readers (semantic HTML, ARIA labels on charts). Automated checks (axe, Lighthouse) catch only part of the problems. Every site gate includes the author's manual keyboard + NVDA check following `docs/accessibility-testing.md`. Feedback from a regular screen-reader user is sought but does not block the P6 gate (author, 2026-10-24): the site says plainly that it hasn't yet been tested by a regular screen-reader user, with a "report a problem" link, until that feedback arrives. When asking the author to test, give exact keystrokes.
- **LLM free quotas are small and unpublished** (Gemini free tier is roughly 100–1,000 RPD by third-party reports, and prompts may be used for training). Cache to disk, batch, send only public aggregates. Tests must not make live LLM calls.
- **NBS terms:** MPI data are for reporting aggregated information only, and an electronic copy of every publication must be sent to the National Data Archive.
- **DHS terms:** use only for the registered project ("Curb Cut: disability prevalence and poverty in Nigeria"); no microdata in any tool or dashboard; send a PDF of every publication to references@dhsprogram.com. GPS coordinates are displaced and stay restricted.
- **Report the poverty result as an adjusted association, not a causal effect.** The pre-registration (DAG, estimand, plan) is committed before outcomes are examined. The GHS analysis is labelled exploratory and underpowered.
- **dbt SQL must work on DuckDB.** Avoid Snowflake-specific functions.

## Corrected facts (don't reintroduce the spec's errors)

- HF `electricsheepafrica/africa-disability-niger` covers **Niger**, not Nigeria; the `-nigeria` variant is a WHO health-indicator mirror. Both are dropped.
- The JONAPWD PDF **does** have a text layer (planning research wrongly said it was scanned). Values come out sorted rather than next to their labels, so validate the label→value mapping by hand against the rendered page. It is "All rights reserved": keep the PDF git-ignored in `data/sources/`, and cite figures rather than redistributing it.
- The "71% vs 62% MPI poor" figure is unverified; compute it from the microdata.
- NPC 2025 state projections aren't public. Denominators come from NBS Demographic Bulletin 2023 Annex 3 (state × sex), cross-checked with WorldPop v3.0 `state_pop_total_scaled.csv` (CC BY 4.0).
- DHS registration is open again (it was reported paused during planning). Nigeria DHS 2024 microdata (full WG-SS) comes from dhsprogram.com, not the World Bank library.
- GHS-Panel is only national/zone-representative. The full WG-SS is in W4 (`s4aq23`–`s4aq33`) and W5 (`s3q23`–`s3q28`); W3 asks only about seeing and walking.
- Render Free cold start is about 1 minute.
- `pymatchit-causal` and `StatsPAI` do exist, but aren't needed. `samplics` is deprecated — use `svy`.
- Check that any other package exists and is maintained before adding it.

## Tooling (set up in P0)

- **Python:** uv workspace, Python 3.12 (`.python-version`; chosen for dbt 1.x / DoubleML / DoWhy / pyfixest compatibility). The root `pyproject.toml` is a virtual workspace root. Members: `packages/disability-access-charts`, `packages/ingest` (`curbcut-ingest`). `packages/transform` is a dbt project, **not** a workspace member; its scripts run in the root environment. `uv sync` installs everything; CI uses `uv sync --locked`. dbt-core 1.12 pulls `dbt-core-experimental-parser`, whose install downloads a wheel from github.com, so `uv sync` needs github.com reachable.
- **Commands:**
  - Lint and type check: `uv run ruff check .`, `uv run ruff format .`, `uv run pyright`.
  - Chart audit: `uv run disability-access-charts check [--strict] site/public/data/charts/*.json` (exit 1 if a chart fails, 2 if a file can't be read). The claim checker's full rules are in `packages/disability-access-charts/docs/claim-checker.md`.
  - Tests: `uv run pytest`. Single test: `uv run pytest packages/disability-access-charts/tests/test_smoke.py::test_version`.
  - JONAPWD extraction (local only; needs the git-ignored PDF): `uv run python -I -m curbcut_ingest.jonapwd <pdf> [--render DIR]`. It writes `data/public/jonapwd/state_disability_type.csv`, which is committed and is what CI uses.
  - Restricted aggregation (local only; needs `data/restricted/` and R): harmonisers `uv run python -I -m curbcut_ingest.restricted.{dhs2024,mpi2021,ghs}` write person-level Parquet to git-ignored `data/restricted/derived/`; `uv run python -I -m curbcut_ingest.aggregate` runs `packages/ingest/R/estimate.R` (R `survey`) and passes every output through the disclosure gate (`curbcut_ingest/disclosure.py`, the only writer to `data/public/aggregates/`; precision flag in `precision.py`). Validation (DHS): `uv run python -I -m curbcut_ingest.validate_ndhs` (reproduces the NDHS report tables from the transcription in `data/public/ndhs_report/`) and `uv run python -I -m curbcut_ingest.crosscheck_svy` (R vs Python `svy`). Full walk-through: `docs/reproduce.md`.
  - Warehouse: `cd packages/transform && uv run dbt deps && uv run dbt build --profiles-dir .` (`dbt deps` installs metaplane `dbt_expectations`). Fixture build (what CI also runs): `uv run dbt build --profiles-dir . --target fixtures --vars '{aggregates_dir: fixtures/aggregates, include_mpi: true, mpi_aggregates_path: fixtures/aggregates/mpi2021_state_national.csv, fixtures: true}'` (writes `data/fixtures.duckdb`; without the vars it silently builds the real aggregates and skips the fixture edge-case test). MPI 2021 is included by default; `--vars '{include_mpi: false}'` leaves it out. (DuckDB file `data/curbcut.duckdb`, git-ignored). Then `uv run python packages/transform/scripts/export_marts.py` (Parquet and `states.json` into `site/public/data/`), `uv run python packages/transform/scripts/build_charts.py` (chart JSON) and `uv run python packages/transform/scripts/build_map.py` (locator map paths from the committed geoBoundaries file in `data/public/geoboundaries/`; fails if any state is missing). The map build's tests are in `packages/transform/tests_py/` (kept out of dbt's `tests/`).
  - Site: `cd site && npm ci && npm run build && npm test` (Playwright + axe against `vite preview` on port 4317 with `--strictPort`; override with `PREVIEW_PORT`). Override the base path with `SITE_BASE`. `prebuild` downloads the DuckDB Parquet extension with a pinned SHA-256, so the build needs network access but the browser never leaves the site's origin.
- **R:** renv at the repo root with `snapshot.type = "explicit"`, so `renv::snapshot()` records only packages listed under `Imports:` in `DESCRIPTION`. Add a package there before snapshotting it.
- **pre-commit:** standard hygiene hooks, ruff, and local hooks that refuse anything under `data/restricted/` or any `*.duckdb` file. `CurbCut.txt` and `renv/activate.R` are excluded from the fixers. Line endings are LF (`.gitattributes`).
- **Publishing:** `.github/workflows/publish-charts.yml` publishes `disability-access-charts` to PyPI via trusted publishing (environment `pypi`) when a `charts-v<version>` tag is pushed; the tag must match the version in its `pyproject.toml`. The library was going to be `a11y-viz`, but PyPI blocks that as too similar to the existing `a11yviz`.
- **CI** (`.github/workflows/ci.yml`): `python` (ruff, pyright, pytest, restricted-data guard) → `data` (dbt build, export, chart JSON, locator map → artifact) → `site` (build, Playwright + axe, Pages artifact) → `deploy` (GitHub Pages, push to `main` only; Pages source is "GitHub Actions", enabled 2026-10-17). CI never needs the PDF or restricted data. Lighthouse CI comes in P6.

P0 verification results go in `docs/verification.md`, each with source URL and date.
