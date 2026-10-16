# Status and handoff

The one page to read first. It says where things stand and what happens next. The rules live in `CLAUDE.md`, the roadmap in `PLAN.md`, and the P0 evidence in `docs/verification.md`. Update this page at every working session and every gate.

**Last updated:** 2026-10-16 · **Current phase:** P1 — thin vertical slice

## Phases

| Phase | State | Gate |
|---|---|---|
| P0 Accounts, checks, bootstrap | ✅ done 2026-10-16 (author sign-off) | CI green ✅ · checks confirmed or decided ✅ · author review ✅ |
| P1 Thin vertical slice | 🟡 in progress | Live URL works by keyboard and with NVDA (author-tested) |
| P2 disability-access-charts 0.1 | ⚪ not started (0.0.1 contrast checks published) | Clean install reproduces examples; LLM mocked in tests |
| P3 Restricted zone + warehouse | ⚪ not started | `dbt build` green on fixtures; disclosure check passes |
| P4 Prevalence | ⚪ not started | Map and comparison live |
| P5 Poverty analysis | ⚪ not started | Pre-registration committed first; brief and results page live |
| P6 API + site polish | ⚪ not started | Accessibility 100 in CI; walkthrough video recorded |
| P7 Launch | ⚪ not started | — |

## Done so far (P0)

- Repo `batestguy/curb-cut` (public): uv workspace, renv, pre-commit restricted-data guard, CI green.
- PyPI name claimed: `disability-access-charts` 0.0.1 (WCAG contrast checks), published via trusted publishing. `a11y-viz` was blocked as too similar to the existing `a11yviz`.
- NBS and World Bank microdata accounts registered.
- **NBS MPI 2021 microdata obtained** (public-use request granted at once). Stored in git-ignored `data/restricted/nbs-mpi-2021/`, with a local hash manifest. The disability module (Section D) covers 213,820 people aged 5+. It includes:
  - the Washington Group Short Set: seeing `d2`, hearing `d3a`, walking `d5`, communicating `d9a`/`d10a`, self-care `d11a`, remembering `d12a`
  - extended items: upper body `d13a`/`d14a`, albinism `d15a`, affect `d16*`
  - assistive technology use `d22*`–`d26*`, including screen readers `d23h`

  Weights `hh_wgt` / `pop_wgt` / `indiv_wgt` are in Section A; senatorial district `a1b` and EA `a4` are there for the design.
- JONAPWD PDF downloaded (git-ignored). It **has a text layer**, so no OCR is needed.
- NBS email sent (2026-10-16) asking about publishing aggregates under an open licence, state-level adequacy, and any further terms.
- NBS 2023 Demographic Bulletin datasheet obtained (git-ignored). Annex 3 gives state × sex 2023 projections; totals validated.
- WorldPop v3.0 confirmed CC BY 4.0, with a ready-made state totals CSV for the cross-check.
- GHS-Panel checked: **W4 and W5 both have all six WG-SS questions**; W3 has only seeing and walking.
- Nigeria DHS 2024 is released, and DHS registration is open again.
- Research checks logged with sources in `verification.md`.

## Blocked / waiting

| Item | Waiting on | Since |
|---|---|---|
| NBS reply on publishing aggregates (sent from Gmail) | NBS | 2026-10-16 |
| DHS account + project request (only if we adopt DHS 2024) | **Author** (account creation) | 2026-10-16 |
| Gemini / Groq real quotas | Accounts (only needed at the alt-text step, P2) | 2026-10-16 |

## Next actions (pick up here)

Session ended 2026-10-16 right after the P0 gate. **Nothing of P1 has been started.**

1. **Author:** create a DHS Program account (https://dhsprogram.com/data/new-user-registration.cfm). Claude cannot create accounts. Then Claude drafts the project request for NG2024DHS (Household Member Recode, which has the disability items `hdis2`–`hdis9`) and shows the text before submitting.
2. **Claude:** download GHS-Panel W4 (World Bank catalog 3557) and W5 (catalog 6410) through the author's logged-in World Bank session in the browser. Tell the author each file's name and size first (already approved in principle on 2026-10-16). Move the files into `data/restricted/ghs-w4/` and `data/restricted/ghs-w5/` with a hash `MANIFEST.md` (same pattern as `data/restricted/nbs-mpi-2021/`). Then count the W4 households re-interviewed in W5, and compare the WG-SS response categories between waves.
3. **Claude: P1 thin vertical slice.** It touches 10+ files, so per the global workflow delegate it to `executor`, then pass the report and diff to `reviewer`. Planned design:
   - **Ingest** (`packages/ingest/`): extract the JONAPWD per-state pages (PDF pages 14–50, Power BI exports; text layer, no OCR) into a tidy CSV `state, disability_type, persons`. pypdf text lists the 10 type labels, then the 10 values in **descending** order. Map label→value by bar position and **validate by rendering pages to PNG** (pypdfium2) and checking a sample by eye. Record page number and PDF SHA-256 per row. The extracted figures are cited as facts, with source © JONAPWD.
   - **Warehouse** (`packages/transform/`, dbt-core 1.x + dbt-duckdb): source → `stg_jonapwd__state_type` → one mart (for example national totals by type, plus state × type). Add a `state_name_aliases` seed: NBS uses "Abia state", "Cross river", "FCT Abuja". The DuckDB file stays git-ignored. Export the marts to `site/data/*.parquet`.
   - **Chart JSON at build time:** a minimal, experimental bar-chart builder in `disability-access-charts`. It outputs a Plotly spec, data-derived alt-text, a data table and a contrast audit (using `contrast.py`), written to `site/data/charts/*.json`. The full API is P2.
   - **Site** (`site/`, Vite, vanilla JS, Plotly.js): semantic HTML. A `<figure>` holds the chart, labelled by the alt-text, with an HTML `<table>` fallback. The chart and table render from the static JSON first. DuckDB-WASM, self-hosted via Vite `?url` imports, loads lazily and powers a native `<select>` "explore by state" table. Keyboard only, no mouse-only interactions. GitHub Pages base path `/curb-cut/`.
   - **CI:** add `dbt build` and a site job (build, Playwright + `@axe-core/playwright`), and deploy to Pages with `actions/deploy-pages`. Pages must be enabled with source "GitHub Actions". Also bump the actions that triggered Node 20 deprecation warnings (checkout, setup-uv, upload/download-artifact). Check that every pinned version exists before using it.
   - **Gate:** the live URL works by keyboard and with NVDA, tested by the author.
4. **Open, not blocking:** NBS reply to the publishing email (comes to the author's Gmail); Gemini and Groq limits (needed in P2).

## Handoff notes

- **Browser:** the author uses Brave with the Claude-in-Chrome extension connected ("Browser 1"). Use those tools in the author's logged-in session. A Brave launched by Playwright with its own profile does **not** share the author's logins. The author is logged in to PyPI, NBS microdata and the World Bank Microdata Library. Never type passwords; ask the author.
- **NBS portal quirk:** on access forms, the Submit button only enables after a real click on "I agree" (`isagree()`). Public-use requests are granted at once. Downloads land in `~/Downloads/Compressed/`.
- **Identity on applications:** Jerry Bannister, independent researcher, NBS account `jzbannister@atbu.edu.ng`. Gmail used for correspondence: batesthommie@gmail.com.
- **Local data** (git-ignored, never commit or send anywhere): `data/restricted/nbs-mpi-2021/` (MPI 2021 Stata files plus `MANIFEST.md`); `data/sources/jonapwd/` (PDF); `data/sources/nbs-demographic-2023/` (xlsx).
- **Release:** bump the version in `packages/disability-access-charts/pyproject.toml` and push tag `charts-v<version>`. Trusted publishing handles the rest.
- **NBS obligation:** send an electronic copy of every publication based on MPI data to the National Data Archive.

## Decisions log

| Date | Decision |
|---|---|
| 2026-10-16 | Revised plan adopted (`PLAN.md`): static site + DuckDB-WASM, two data zones, MPI 2021 as the main source. |
| 2026-10-16 | Chart library renamed `disability-access-charts` (`a11y-viz` unavailable on PyPI). |
| 2026-10-16 | JONAPWD ingest uses text extraction, not OCR. |
| 2026-10-16 | Applications describe the author as an independent researcher. |
| 2026-10-16 | All of `data/sources/` is git-ignored (third-party files are "All rights reserved"). |
| 2026-10-16 | **P0 gate passed.** Nigeria DHS 2024 is adopted as a second prevalence source next to MPI 2021. The exploratory panel uses GHS W4→W5 (all six WG-SS domains). |
