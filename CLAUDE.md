# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

Phase **P0** (accounts, checks, bootstrap) is in progress. The repo scaffold and tooling exist; the account and verification checks in `docs/verification.md` are still open.

- **`PLAN.md` is the source of truth** (agreed 2026-10-16). Read the section for the current phase before starting work.
- `CurbCut.txt` is the original spec, kept for the record. Where it disagrees with `PLAN.md`, `PLAN.md` wins — many of its claims turned out wrong (see "Corrected facts").

Update this file as real commands and structure appear, and replace the "intended" items with what actually got built.

## What the project is

Curb Cut is a zero-cost, accessible data platform for Nigerian disability data, and a portfolio piece aimed at recruiters across data roles (see the recruiter-track table in `PLAN.md`). The author has lived experience with disability and assistive technology; that story and their manual NVDA/keyboard testing are central, not decoration.

Public GitHub repo `curb-cut`, MIT. Main components:

- **`disability-access-charts`** (Python, PyPI): accessible Plotly wrapper. Palettes, contrast checks (WCAG 2.2 SC 1.4.3 / 1.4.11), `audit(fig)` that runs in CI, `theme()`, an `disability-access-charts check` CLI, **alt-text checked against the data**, and a **data-table fallback** for every chart. It must stand apart from the existing `maidr` library. Data-derived alt-text is the default; LLM polish (Gemini → Groq) is optional, number-checked, cached, and only ever sees public aggregates.
- **Ingest:** OCR of the JONAPWD 2025 PDF (scanned — needs docling/Tesseract, not pdfplumber), NBS MPI 2021 microdata (the main source), GHS-Panel W3–W5, NBS 2023 Demographic Bulletin projections, WorldPop and geoBoundaries (CC BY).
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

Never commit microdata, never send it to an LLM or any external service, and never write a public output that skips the disclosure check.

## Hard constraints

- **$0/month, always.** Never introduce a paid service. HF Gradio/Docker Spaces need a paid plan; static Spaces are free. Neon/Supabase are cut.
- **No committed DuckDB file.** Public data ships as Parquet inside the Pages site (1 GB site limit; git warns over 50 MiB and rejects over 100 MiB). Do not use GitHub Release assets for data: they lack CORS headers, so DuckDB-WASM can't read them. DuckDB allows one writer at a time — no concurrent writers in CI or scripts.
- **Phase order is fixed (P0–P7 in `PLAN.md`). Stop at every phase gate for the author's review.** Scope creep is the main way this project fails. After each phase, update the README hero links and add a CHANGELOG entry (conventional commits).
- **Accessibility is a requirement.** Keyboard only (Tab reaches everything, no mouse-only interactions) and screen readers (semantic HTML, ARIA labels on charts). Automated checks (axe, Lighthouse) catch only part of the problems; the author's manual NVDA sign-off is part of each relevant gate.
- **LLM free quotas are small and unpublished** (Gemini free tier is roughly 100–1,000 RPD by third-party reports, and prompts may be used for training). Cache to disk, batch, send only public aggregates. Tests must not make live LLM calls.
- **Report the poverty result as an adjusted association, not a causal effect.** The pre-registration (DAG, estimand, plan) is committed before outcomes are examined. The GHS analysis is labelled exploratory and underpowered.
- **dbt SQL must work on DuckDB.** Avoid Snowflake-specific functions.

## Corrected facts (don't reintroduce the spec's errors)

- HF `electricsheepafrica/africa-disability-niger` covers **Niger**, not Nigeria; the `-nigeria` variant is a WHO health-indicator mirror. Both are dropped.
- The JONAPWD PDF has no text layer — OCR it and measure accuracy by hand-checking a sample.
- The "71% vs 62% MPI poor" figure is unverified; compute it from the microdata.
- NPC 2025 state projections aren't public; use NBS Demographic Bulletin 2023, cross-checked with WorldPop.
- DHS registration is paused; use published DHS tables as a benchmark only.
- GHS-Panel is only national/zone-representative; the full disability set is W5 only (W3 asks seeing and mobility).
- Render Free cold start is about 1 minute.
- `pymatchit-causal` and `StatsPAI` do exist, but aren't needed. `samplics` is deprecated — use `svy`.
- Check that any other package exists and is maintained before adding it.

## Tooling (set up in P0)

- **Python:** uv workspace, Python 3.12 (`.python-version`; chosen for dbt 1.x / DoubleML / DoWhy / pyfixest compatibility). Root `pyproject.toml` is a virtual workspace root; members live in `packages/*` (currently only the `disability-access-charts` stub). `uv sync` installs everything; CI uses `uv sync --locked`.
- **Commands:** `uv run ruff check .`, `uv run ruff format .`, `uv run pyright`, `uv run pytest`. Single test: `uv run pytest packages/disability-access-charts/tests/test_smoke.py::test_version`.
- **R:** renv at the repo root with `snapshot.type = "explicit"`, so `renv::snapshot()` records only packages listed under `Imports:` in `DESCRIPTION`. Add a package there before snapshotting it.
- **pre-commit:** standard hygiene hooks, ruff, and local hooks that refuse anything under `data/restricted/` or any `*.duckdb` file. `CurbCut.txt` and `renv/activate.R` are excluded from the fixers. Line endings are LF (`.gitattributes`).
- **Publishing:** `.github/workflows/publish-charts.yml` publishes `disability-access-charts` to PyPI via trusted publishing (environment `pypi`) when a `charts-v<version>` tag is pushed; the tag must match the version in its `pyproject.toml`. The library was going to be `a11y-viz`, but PyPI blocks that as too similar to the existing `a11yviz`.
- **CI** (`.github/workflows/ci.yml`): uv sync, a restricted-data guard, ruff, pyright, pytest with coverage. dbt build on fixtures, axe and Lighthouse jobs are added in P1.

Still to come: dbt (`dbt build` / `dbt test` on synthetic fixtures), the Vite site with Playwright + axe and Lighthouse CI,

P0 verification results go in `docs/verification.md`, each with source URL and date.
