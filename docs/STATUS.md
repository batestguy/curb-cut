# Status and handoff

The one page to read first. It says where things stand and what happens next. The rules live in `CLAUDE.md`, the roadmap in `PLAN.md`, and the P0 evidence in `docs/verification.md`. Update this page at every working session and every gate.

**Last updated:** 2026-10-17 · **Current phase:** P1 — thin vertical slice (built and live; awaiting author gate)

## Phases

| Phase | State | Gate |
|---|---|---|
| P0 Accounts, checks, bootstrap | ✅ done 2026-10-16 (author sign-off) | CI green ✅ · checks confirmed or decided ✅ · author review ✅ |
| P1 Thin vertical slice | 🟡 built and live — **awaiting author keyboard + NVDA check** | Live URL works by keyboard and with NVDA (author, per `docs/accessibility-testing.md`) |
| P2 disability-access-charts 0.1 | ⚪ not started (0.0.1 contrast checks published) | Clean install reproduces examples; LLM mocked in tests |
| P3 Restricted zone + warehouse | ⚪ not started | `dbt build` green on fixtures; disclosure check passes |
| P4 Prevalence | ⚪ not started | Map and comparison live |
| P5 Poverty analysis | ⚪ not started | Pre-registration committed first; brief and results page live |
| P6 API + site polish | ⚪ not started | Accessibility 100 in CI; walkthrough video recorded; feedback from a regular screen-reader user acted on |
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

## Done in P1 (2026-10-17)

- **Live site: https://batestguy.github.io/curb-cut/**, deployed by CI on every push to `main`.
- JONAPWD state figures extracted from the PDF text layer into `data/public/jonapwd/state_disability_type.csv`. That is 370 rows: 37 states × 10 types. Two page layouts are handled. Bar lengths are checked against the values. 7 pages (70 values) were checked by eye against renders, and a re-run gives a byte-identical file. The per-state sum is 34,901,406; JONAPWD prints 34,901,403. The difference is left as printed and disclosed on the page.
- dbt project `packages/transform` (dbt-core 1.12.6 + dbt-duckdb 1.11.0): source CSV → `stg_jonapwd__state_type` → two marts. Seeds: `dim_states` (ISO codes and zones verified), `state_name_aliases`. 51 tests pass.
- `disability_access_charts.experimental.bar_chart`: Plotly spec, data-derived alt-text checked against the data, table, and contrast audit.
- Site (`site/`, Vite + Plotly basic + DuckDB-WASM, all self-hosted). 9 Playwright + axe tests pass: WCAG 2.2 AA light and dark, keyboard, accessible names, table semantics, 320 px, same-origin only, failure paths. CI is green on Linux, including the deploy. A live check by keyboard (Lagos) worked, and the page contacted only `batestguy.github.io`.
- Reviewed by `reviewer`. Review fixes applied: chart description read once, chart failure announced, `<noscript>` link to the CSV, "likely because of rounding" wording.
- GHS-Panel W4 and W5 downloaded (`data/restricted/ghs-w4`, `ghs-w5`, with hash manifests). WG-SS uses the same 4 categories in both waves; W4 adds a "too young" code (−1), to be set to missing. **4,735 households are in both waves**: 98% have the same state, 97% the same EA. That is enough for the W4→W5 panel.
- DHS project "Curb Cut: disability prevalence and poverty in Nigeria" (project 246118): **Survey and GPS access approved 2026-10-16** (authorization letter AuthLetter_246118.pdf is in the author's Gmail). **Downloaded 2026-10-17** into `data/restricted/dhs-2024/` (`pr/NGPR8BFL.dta`, `hr/NGHR8BFL.dta`, with a hash manifest; ZIP sizes match the DHS API). The PR file has 176,045 people. The full WG-SS is asked of 149,380 people aged 5+: `hdis2` seeing, `hdis4` hearing, `hdis5` communicating, `hdis6` remembering, `hdis7` walking, `hdis8` self-care, each in 4 categories plus 8 = don't know. `hdis9` is the highest degree across domains; `hdis1`/`hdis3` record glasses and hearing aid use. Design: weight `hv005` (÷1,000,000), PSU `hv021`, strata `hv022`/`hv023`, state `shstate` (37 values), plus `hv025` urban/rural, `hv104` sex, `hv105` age, `hv270` wealth quintile. GPS points are displaced (urban up to 2 km, rural up to 5 km, 1% up to 10 km), so never use them for distances or small areas, and never publish them.

## Blocked / waiting

| Item | Waiting on | Since |
|---|---|---|
| **P1 gate: keyboard + NVDA check of the live site (`docs/accessibility-testing.md`)** | **Author** | 2026-10-17 |
| NBS reply on publishing aggregates | NBS | 2026-10-16 |
| Gemini / Groq real quotas | Accounts (P2) | 2026-10-16 |

## Next actions (pick up here)

1. **Author:** install NVDA (free, nvaccess.org) and follow `docs/accessibility-testing.md` on https://batestguy.github.io/curb-cut/. Report anything confusing. Passing this check is the P1 gate.
2. ✅ DHS 2024 downloaded and checked (see Done in P1). The data for P3/P4 is now complete: MPI 2021, DHS 2024, GHS W4/W5.
3. **After the P1 gate:** P2, `disability-access-charts` 0.1. Carry over these follow-ups:
   - Alt-text checks should also verify *which* category each number belongs to, not just that the number exists (review finding 8).
   - Decide whether the state `<select>` should query on every arrow key or use a "Show figures" button (review finding 6).
4. **P6 follow-ups:**
   - Pre-render the national table into the HTML at build time. First paint measured 4.8 s on the author's connection, against a 3 s target.
   - The chart shows only 2 axis ticks at 320 px.
   - `dist` is 74 MB (both DuckDB bundles), but each visitor downloads only one, about 8 MB gzip, and only after choosing a state.

## Handoff notes

- **Browser:** the author uses Brave with the Claude-in-Chrome extension connected ("Browser 1"). Use those tools in the author's logged-in session. A Brave launched by Playwright with its own profile does **not** share the author's logins. The author is logged in to PyPI, NBS microdata and the World Bank Microdata Library. Never type passwords; ask the author.
- **NBS portal quirk:** on access forms, the Submit button only enables after a real click on "I agree" (`isagree()`). Public-use requests are granted at once. Downloads land in `~/Downloads/Compressed/`.
- **Identity on applications:** Jerry Bannister, independent researcher, NBS account `jzbannister@atbu.edu.ng`. Gmail used for correspondence: batesthommie@gmail.com.
- **Local data** (git-ignored, never commit or send anywhere): `data/restricted/nbs-mpi-2021/` (MPI 2021 Stata files plus `MANIFEST.md`); `data/restricted/dhs-2024/` (DHS PR/HR recodes plus manifest); `data/restricted/ghs-w4/`, `data/restricted/ghs-w5/` (GHS-Panel Stata files plus manifests; the W4 disability file is `sect4a_harvestw4.dta`, the W5 one is `Post Planting Wave 5/Household/sect3_plantingw5.dta`); `data/sources/jonapwd/` (PDF); `data/sources/nbs-demographic-2023/` (xlsx).
- **Release:** bump the version in `packages/disability-access-charts/pyproject.toml` and push tag `charts-v<version>`. Trusted publishing handles the rest.
- **NBS obligation:** send an electronic copy of every publication based on MPI data to the National Data Archive.
- **DHS obligation:** send a PDF of every report or publication using DHS data to references@dhsprogram.com. DHS data may be used only for the registered project. A new purpose needs a new DHS project.

## Decisions log

| Date | Decision |
|---|---|
| 2026-10-16 | Revised plan adopted (`PLAN.md`): static site + DuckDB-WASM, two data zones, MPI 2021 as the main source. |
| 2026-10-16 | Chart library renamed `disability-access-charts` (`a11y-viz` unavailable on PyPI). |
| 2026-10-16 | JONAPWD ingest uses text extraction, not OCR. |
| 2026-10-16 | Applications describe the author as an independent researcher. |
| 2026-10-16 | All of `data/sources/` is git-ignored (third-party files are "All rights reserved"). |
| 2026-10-17 | Gate wording changed: the author (new to screen readers) does a scripted keyboard + NVDA check at each site gate; the P6 gate adds feedback from a regular screen-reader user. |
| 2026-10-17 | P1 built by `executor`, reviewed by `reviewer` (merge after fixes), fixes applied, merged and deployed to GitHub Pages. |
| 2026-10-16 | **P0 gate passed.** Nigeria DHS 2024 is adopted as a second prevalence source next to MPI 2021. The exploratory panel uses GHS W4→W5 (all six WG-SS domains). |
