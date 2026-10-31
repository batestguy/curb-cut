# Status and handoff

The one page to read first. It says where things stand and what happens next. The rules live in `CLAUDE.md`, the roadmap in `PLAN.md`, and the P0 evidence in `docs/verification.md`. Update this page at every working session and every gate.

**Last updated:** 2026-10-31 · **Current phase:** **P4 done: the P4b gate passed 2026-10-30** (author: "pass"; PR #3): 37 state pages live, `disability-access-charts` 0.2.0 on PyPI. **P5 in progress** on branch `p5-poverty` (plan agreed 2026-10-30, `PLAN.md` steps 15–21): steps 15–16 done; step 17: pre-registration revision 3 awaits the author's final read, then code freeze and OSF registration; the analysis code is written and reviewed (synthetic data only) and the section 5.6 exposure check passed on 2026-10-31 (S2 11.07% vs NBS 11.0%). No outcome by disability has been computed. DHS and NBS publication copies for the site as of 2026-10-30 sent by the author on 2026-10-30 (PDF of all 40 pages; NBS copy to Feedback@nigerianstat.gov.ng, the catalogue's data-access contact, as no archive address is listed). Still owed: P1's NVDA check (before P6). P4a gate passed 2026-10-29 (PR #2 merged); P4b plan agreed 2026-10-29, step 10 (law facts, D25) done; P4 planned 2026-10-27 (`PLAN.md` → P4: P4a numbers, map and comparison; P4b chart library 0.2 and state pages); P4a step 0 done 2026-10-27 (the pipeline reproduces the NDHS report tables; R and svy agree, `verification.md` D48); step 1 (direct estimates) next. `disability-access-charts` 0.1.0 is on PyPI (2026-10-22). P1 is live; its NVDA check is deferred.

## Phases

| Phase | State | Gate |
|---|---|---|
| P0 Accounts, checks, bootstrap | ✅ done 2026-10-16 (author sign-off) | CI green ✅ · checks confirmed or decided ✅ · author review ✅ |
| P1 Thin vertical slice | 🟡 built and live; keyboard pre-check passed 2026-10-17. **The author's NVDA check is deferred (author, 2026-10-17)**: do it before the P6 gate at the latest | Live URL works by keyboard and with NVDA (author, per `docs/accessibility-testing.md`) |
| P2 disability-access-charts 0.1 | ✅ done 2026-10-22: 0.1.0 published (tag `charts-v0.1.0`, pushed by the author); a clean install from PyPI ran all 3 examples and `check` | Clean install reproduces examples; LLM mocked in tests |
| P3 Restricted zone + warehouse | ✅ done 2026-10-24 (author): PR #1 merged, CI green; all aggregates incl. MPI 2021 public | `dbt build` green on fixtures; disclosure check passes |
| P4 Prevalence | ✅ P4a passed 2026-10-29; P4b passed 2026-10-30 (author): 37 state pages live, 0.2.0 on PyPI | P4a: map and comparison live · P4b: state pages live, 0.2 on PyPI |
| P5 Poverty analysis | 🟡 in progress: steps 15–16 done; step 17 (pre-registration) **frozen 2026-10-31 at tag `p5-freeze`** (commit 22b8ace; section 11 filled in 55f9fe4) and **waiting on the author's OSF registration**. Analysis code written and reviewed twice, synthetic data only; the 5.6 exposure check passed (S2 11.07% vs NBS 11.0%). No outcome by disability has been computed. Details: Next actions → "P5: pick up here" | Pre-registration committed first; brief and results page live |
| P6 API + site polish | ⚪ not started | Accessibility 100 in CI; walkthrough video recorded; author's NVDA check; regular screen-reader user's feedback sought, not blocking (2026-10-24); acted on |
| P7 Launch | ⚪ not started | — |

## Done so far (P0)

- Repo `batestguy/curb-cut` (public): uv workspace, renv, pre-commit restricted-data guard, CI green.
- PyPI name claimed: `disability-access-charts` 0.0.1 (WCAG contrast checks), published via trusted publishing. `a11y-viz` was blocked as too similar to the existing `a11yviz`.
- NBS and World Bank microdata accounts registered.
- **NBS MPI 2021 microdata obtained** (public-use request granted at once). Stored in git-ignored `data/restricted/nbs-mpi-2021/`, with a local hash manifest. The disability module (Section D) covers 213,820 people aged 5+. It includes:
  - items close to, but not, the Washington Group Short Set (`verification.md` D39, D43): seeing `d2`, hearing `d3a`, walking `d5` (yes/no screeners; severity only for aid users), communicating `d9a`/`d10a`, self-care `d11a`, remembering `d12a`
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
- **Automated NVDA run, 2026-10-17** (NVDA 2026.2 via Guidepup 0.35.0 + Playwright, Chromium, live site; script kept outside the repo, in the session scratchpad). Spoken output confirmed:
  - skip link first, and it works
  - clean heading structure
  - the chart's description is read once, with its numbers
  - tables announced with size and caption, every number read with its headers
  - the picker is labelled "State, combo box"
  - choosing a state says "Loading figures for …", and the state table works with Ctrl+Alt+arrows

  **Not heard:** the completion message "Showing 10 disability types for …". The page displayed it, but NVDA didn't speak it within 30 s. Confirm by ear. First state load takes ~10 s (7.8 MB DuckDB wasm plus extension).
- Reviewed by `reviewer`. Review fixes applied: chart description read once, chart failure announced, `<noscript>` link to the CSV, "likely because of rounding" wording.
- GHS-Panel W4 and W5 downloaded (`data/restricted/ghs-w4`, `ghs-w5`, with hash manifests). WG-SS uses the same 4 categories in both waves; W4 adds a "too young" code (−1), to be set to missing. **4,735 households are in both waves**: 98% have the same state, 97% the same EA. That is enough for the W4→W5 panel.
- **Keyboard pre-check of the live site after the map change, 2026-10-17** (Claude, real key presses in the author's Brave, commit f64481d deployed). This is not the gate check, which stays with the author.
  - **Passed:**
    - The skip link is the first stop, visible, and moves focus to `<main>`.
    - Tab order: picker → Show figures → card (heading, then map, then the card's source links) → footer links → back to the skip link. No trap, and an outline on every stop.
    - Typing "Lagos" loads nothing. Show figures builds the card, with focus on the "Lagos" heading. The card has no JONAPWD row.
    - Tab onto the map opens the box ("Lagos, 2,142,658 people: 6.1% … ranked 2 of 37"), and Esc closes it.
    - Mouse hover on Borno outlines it and shows its figure; the box closes when the mouse leaves.
    - The chart highlight moves from Lagos to Kano. Ekiti has no slogan line.
    - The map's accessible name carries the figure.
  - **Cosmetic:** while the box is open under Lagos, it covers the "Boundaries: geoBoundaries" caption.
  - **Not checked:**
    - 400% zoom and window resizing (Brave wouldn't resize; the 320 px Playwright test covers the narrow layout).
    - The flag band in dark mode (an OS setting).
    - NVDA. Two automated Guidepup runs failed because the author's other open windows took keyboard focus, so the keystrokes went elsewhere. They were stopped, and no NVDA result is claimed.
- **"Show figures" button and announcement (commit 36f5ca4):** the picker no longer queries on every change; DuckDB warms up when the picker or button is first focused; after a press, focus moves to the result. Both still need checking **by ear** with NVDA at the P1 gate.
- **Nigerian visual identity and state card (2026-10-17, commit 119cf4e, deployed by CI run 39004343042, all jobs green):**
  - Flag green is the brand colour. Light: `#006b3f` for text, links and focus (6.6:1), `#008751` for the band, heading rules and bars (4.6:1). Dark: `#6fd6a0` for text, links and focus (10.5:1), `#198754` for bars (4.1:1). A decorative green-white-green band (`aria-hidden`, with a thin grey frame so the white stripe shows on a white page) sits above the header, and the favicon has the same stripes. The caveat keeps its amber.
  - Chart library: `DEFAULT_THEMES` gains a `highlight` colour, deep indigo `#1b1464` in light mode and gold `#ffe08a` in dark (3.45:1 and 3.51:1 against the green bars). The audit checks it against both the background and the bars (SC 1.4.11), with tests. **Deviation from the plan:** the dark-mode bars are a mid green, not a light one. With light green bars, the only highlight colours 3:1 from both the bars and `#121212` are dim mid-tones (e.g. crimson `#c31e55`, 3.2:1), which look darker rather than selected. A mid green with a light gold highlight stands out more. (The review corrected an earlier, wrong claim that no such colour exists.)
  - New chart "All types, by state" (37 bars, via `bar_chart`, so it has data-checked alt-text, a table and an audit). The chosen state's bar gets the highlight colour, a thick outline, and a bold label and value. The chart's accessible name doesn't change.
  - State card after "Show figures": capital, zone, 2023 population (NBS Annex 3), slogan when sourced (35 of 37; Ekiti and Osun are left blank because the sources disagree), JONAPWD total with its share and rank of 37, a sources line, and a locator map. The card and chart both say JONAPWD's figures are about 15% of population, so the ranking mostly follows population (JONAPWD ÷ NBS 2023 population ranges from 13.9%, Jigawa, to 16.5%, FCT). Focus moves to the card's heading; the table follows.
  - Locator map: geoBoundaries simplified ADM1, committed in `data/public/geoboundaries/` (828 KB, CC BY 4.0). `build_map.py` projects it, simplifies it to 50 KB (17 KB gzip) and fails if a state is missing or its code disagrees. Small states (Lagos, FCT, Anambra and others) also get a ring. The map is one `role="img"` named "Map of Nigeria with <state> highlighted, in the <zone> zone", with the SVG hidden.
  - dbt: seed `state_facts` and mart `mart_state_profile` (exported into `states.json`), plus an alias for geoBoundaries' FCT name. dbt: 69 data tests pass (51 before). Also passing: 54 pytest, 17 Playwright + axe tests (light and dark, including a map-failure test), ruff, pyright and pre-commit. Reviewed by `reviewer`: no blocking issues. Fixed: a corrected dark-theme rationale, zone cited (D16), a population caveat on the rank, a map timeout, the card no longer a nested landmark, and the highlight re-synced if the chart loads late.
- DHS project "Curb Cut: disability prevalence and poverty in Nigeria" (project 246118): **Survey and GPS access approved 2026-10-16** (authorization letter AuthLetter_246118.pdf is in the author's Gmail). **Downloaded 2026-10-17** into `data/restricted/dhs-2024/` (`pr/NGPR8BFL.dta`, `hr/NGHR8BFL.dta`, with a hash manifest; ZIP sizes match the DHS API). The PR file has 176,045 people. The full WG-SS is asked of 149,380 people aged 5+: `hdis2` seeing, `hdis4` hearing, `hdis5` communicating, `hdis6` remembering, `hdis7` walking, `hdis8` self-care, each in 4 categories plus 8 = don't know. `hdis9` is the highest degree across domains; `hdis1`/`hdis3` record glasses and hearing aid use. Design: weight `hv005` (÷1,000,000), PSU `hv021`, strata `hv022`/`hv023`, state `shstate` (37 values), plus `hv025` urban/rural, `hv104` sex, `hv105` age, `hv270` wealth quintile. GPS points are displaced (urban up to 2 km, rural up to 5 km, 1% up to 10 km), so never use them for distances or small areas, and never publish them.

## Blocked / waiting

| Item | Waiting on | Since |
|---|---|---|
| **P1 gate: keyboard + NVDA check of the live site (`docs/accessibility-testing.md`)** | **Author** | 2026-10-17 |
| Gemini / Groq real quotas | Accounts (P2) | 2026-10-16 |

## Next actions (pick up here)

### P5: pick up here (2026-10-31)

**State:** pre-registration revision 3 approved by the author and frozen (tag `p5-freeze`, commit `22b8acee`); section 11 records the approval, the tag, the commit and the SHA-256 of the pre-registration, `uv.lock` and `renv.lock` as frozen. Branch `p5-poverty` and the tag are pushed. **Nothing has linked poverty to disability or to any confounder.** The real-data CLIs (`p5_mpi --real`, `p5_ghs --real`) refuse until section 11 holds an OSF URL.

**Next, in order:**
1. **Author: register on OSF** (Secondary Data Preregistration template). Answers to paste: `docs/osf-registration.md` (written from memory of the template's parts; paste each under the closest question). Attach `docs/preregistration.md` as frozen: `git show p5-freeze:docs/preregistration.md > preregistration-p5-freeze.md` (SHA-256 `65d0a4b2…e82955`). Then give Claude the OSF URL and timestamp.
2. **Claude:** add the OSF URL and timestamp to section 11 (the only part that may change after the freeze), commit, push.
3. **Real run** (local, long: 3,000 synthetic households took 38 min at the pre-registered sizes; 52,022 real households may take many hours; results are checkpointed after each step): `uv run python -I -m curbcut_ingest.restricted.mpi2021_poverty --validate` (rebuild check), `uv run python -I -m curbcut_ingest.restricted.p5_exposure --check`, then `uv run python -I -m curbcut_ingest.restricted.p5_mpi --real` and `uv run python -I -m curbcut_ingest.restricted.p5_ghs --real`. Check `status` in `results.json`: `complete_with_errors` lists `failed_steps` (exit 1).
4. **Table 7 check first** (pre-registered stop rule, section 5.6/7): S2 shares vs NBS 71.4/61.8, gap 9.6 ± 2.0.
5. Then the brief and results page (PLAN step 19+), through the disclosure gate; a deviations section (pre-registration section 10) for anything that departs from the plan; publication copies to DHS (not used in P5) and NBS.

**What the reviews left for the author to know** (not defects): primary exposure is rare (688 households, 1.33% of people), so the interval may be wide and "inconclusive" is a real outcome under the ±2-point rule; the GHS W4 farm item probably includes helpers while W5's helping item was dropped (D5), which may lower W5 farm work slightly (wording differences are reported with the result).

**Exposure check record (section 2.2 item 9):** first run failed (S2 14.26%, every screener "yes" counted); a severity-only diagnostic gave 5.65%; the author adopted reading C (NBS footnote 19, "even when using equipment") before running it; re-run 11.07% (pass), repeated on the frozen commit with the same numbers. Primary 1.33, S3 0.61, S5 8.78, S6 0.92.

### P4b gate passed (2026-10-30)

**Gate evidence:** CI green on PR #3; 561 Python and 98 site tests; `check --strict` on 41 chart documents; review findings fixed (tables reachable by keyboard at 320 px, findings compare the state's own activities, unreliable cells hidden, skip link past the state table). A scripted NVDA transcript (Guidepup, NVDA, Chrome; Edo, which has suppressed cells) confirmed: 22 Tab stops in a sensible order, 14 headings in order, both graphics named (the dot plot's data-derived description; the locator map), all 6 tables announce caption and size, wealth cells read with their headers including "not shown: too few respondents", "not shown: withheld so a neighbouring small cell can't be worked out" and "not shown: too imprecise (unreliable)", Edo's own wealth details open with Enter; on the main page "Skip the state table" lands on the next heading and the state picker is 5 Tabs on, and a map-table link reads "row 2, State, column 1, Abia, link". The script could not capture the picker's full announcement; the author checked the main page and a state page by hand and passed the gate. **Next: P5.** DHS and NBS publication copies sent 2026-10-30.

### P4b progress (2026-10-30)

**Step 11 (chart library 0.2) done** on branch `p4b-charts-pages`, review fixes committed and pushed; the checks are in the decisions log. The built wheel installs clean on Python 3.12 (core and `[plotly]`) and 3.10 (core and `[plotly]`): every example runs and its chart documents pass `check --strict`. **Step 12 done (2026-10-30):** the author said go ahead; Claude pushed `charts-v0.2.0` (on 6d778e8); the publish workflow passed; a clean install of 0.2.0 from PyPI on Python 3.12 (`[plotly]`) and 3.10 (core) ran every example, and `check --strict` passed. **Next: step 13**, the 37 state pages. Accessible places per state was checked and dropped (D60).

**Step 13 (37 state pages) built (2026-10-30), awaiting review.** `build_state_pages.py` writes `site/states/<slug>.html` (slug: lower case, other characters to hyphens, so `federal-capital-territory`) and `states/index.html` from the warehouse; each page's activity chart is a `dot()` document (`site/public/data/charts/states/<slug>.json`, `check --strict` in CI) drawn as a static SVG; share images come from `npm run build` (prebuild). Pages are about 42 KB of HTML and about 51 KB in all (budget 60 KB / 150 KB). Wealth is shown by the state's zone, with the state's own cells behind a disclosure (STATUS step 1 note). The main page's map table now links each state (37 Tab stops); a "Skip the state table" link before it (the 9th stop after `<main>`) jumps them, so the picker is 5 stops after the skip (14 in all), or the 51st stop without it (both counted exactly in `site.spec.js`). Review fixes (same day): every table is a focusable region; unreliable cells are not shown anywhere (5–17 included); suppressed cells say whether they had too few respondents or were withheld (complementary suppression); estimates under 0.05% read "<0.1"; the activity chart shows the state alone, so findings and alt-text compare only its own activities (the library has no per-activity reference; Nigeria's figures are in a table under it); the build fails on a page over 60 KB. The "not yet tested by a regular screen-reader user" notice and "report a problem" link (GitHub issues, needs an account) are on the state pages only; the main page does not have them yet. **Next:** review, then the P4b gate (step 14).

### P4a gate passed (2026-10-29)

**Gate evidence:** CI green on PR #2, review findings fixed, 481 Python and 33 site tests pass, `check --strict` passes on all 4 charts. A scripted NVDA transcript (Guidepup, NVDA 2026.2, Chrome) confirmed the skip link, 11 Tab stops to the state picker, the map's single stop and spoken description, Esc on the tip, the details toggle, the heading order on both pages, table captions and cells read with their headers, the state picker (K to Kano), and the map tip after Shift+Tab. The transcript could not capture what NVDA says when the state card loads; **the author checked that by hand and it reads fine.** The author did not report any problem with the map colours. **Next: P4b** (`PLAN.md` → P4b: chart library 0.2 with map support, 37 state pages). Still owed: P1's NVDA check (before P6), and a regular screen-reader user's feedback (P6, not blocking).

### P4a progress (2026-10-27)

**Step 1 (direct estimates) done.** Commits 2de1589 (code), f95b475 (complementary suppression), b7f113e (data). Every aggregate CSV now has `breakdown` / `breakdown_level` (`all` / `all` where there is none). New DHS cells: state × sex, a zone file (`dhs2024_zone.csv`: overall, by sex), and urban/rural and wealth quintile (`hv270`) at national, zone and state level, plus age bands (DISABILITY3, national and zone). Every earlier cell has identical values (the files gained two columns). `dhs2024_state.csv` 5,138 cells (413 suppressed, all state × wealth quintile: 168 under 30 and 245 secondary, so that none can be recovered by subtraction; 16 states); `dhs2024_national.csv` 197; `dhs2024_zone.csv` 894. `validate_ndhs` reproduces all 1,360 transcribed report cells, now including the zone, urban/rural and (men's) wealth-quintile rows, which confirms the `hv270` direction; `crosscheck_svy` covers all 5,816 published DHS cells (estimates equal, unweighted n equal, SEs within 2.2%). dbt: new `mart_prevalence_breakdowns`; the existing marts keep `breakdown = 'all'`; the site data are byte-identical. State × wealth is mostly `review`/`unreliable` (DISABILITY3 18+: 82 of 183 cells reliable, 30 suppressed), so the state pages should show wealth by zone and say why.

**Update 2026-10-28:** draft PR #2 opened for `p4a-prevalence` so CI runs on the branch (it merges at the P4a gate). The covariate candidates and the pre-declared selection rule are written in `docs/fay-herriot-covariates.md` (D50–D54); **the author approved all five and the rule on 2026-10-28**, so they are frozen. Covariates C1–C5 built and reviewed. C4 is MICS literacy of women 15–49, because MICS has no state figures for 15–24 (author, D53). **FH result (D56): no pre-declared arcsine-normal model passes the diagnostics, and FH would add only a negligible precision gain (γ ≈ 0.95, median 4%; reviewed). The author chose the direct estimates as the headline; FH is published as a result.** Next: step 3 (spatial analysis on the direct estimates), then steps 4–6 (export, main page, P4a gate).

**Update 2026-10-29: steps 4 and 5 built (not yet gated).** Step 3 (spatial, D58) done 2026-10-28. Step 4: dbt sources/staging for the spatial outputs and NDHS Table 14.1, seed `reference_figures`, marts `mart_prevalence_comparison`, `mart_spatial_state`, `mart_spatial_moran`; `export_marts.py` writes the DHS Parquet plus `prevalence.json` and `spatial.json`. Step 5: the main page leads with the DHS 2024 18+ national figure; comparison (JONAPWD 15% assumed, WHO 16% as WHO words it (D59), NDHS 15+ 15.5% any difficulty vs 2.8% cut-off, ours 18+); map in fixed classes (<2, 2–3, 3–4, 4–6, 6%+; counts 12/11/4/6/4, none empty) built with the experimental `disability_access_charts.maps.choropleth` (not exported, no version bump); 37-state dot plot with intervals; spatial sentences (no hotspots, so no outlines); DHS figure on the state card; `site/methodology.html`. JONAPWD moved below as "What was assumed". **Next: step 6, the P4a gate: the author's keyboard + NVDA check of the new sections, then merge PR #2.**

**Pick up here (handoff 2026-10-27):** branch `p4a-prevalence` is pushed (cebfe2d), not merged. **Step 2 (Fay-Herriot) starts with the author's sign-off on the covariate list**, written before any model is fitted (`PLAN.md` P4a step 2): Claude drafts the candidates (share aged 60+, urban share, MPI poverty headcount, female literacy or schooling, population density), each with a public state-level source, year and licence, and a D-row; the author approves; then BIC selection (at most 2-3), arcsine FH, smoothed variances, benchmarking, bootstrap MSE, spatial FH comparison. Optional cleanup: ask GitHub Support to purge the unreferenced commit df12d47 (D49).

**Step 2 (Fay-Herriot) needs:** the direct DISABILITY3 18+ state estimates and SEs (`dhs2024_state.csv`, `breakdown = 'all'`, `sex = 'all'`; all 37 reliable) as inputs; the covariate candidate table with a D-row per covariate written down **before** fitting (share 60+, urban share, MPI poverty headcount, female literacy or schooling, density); a GVF for the sampling variances; and the `sae` / `emdi` fitness check (D47). Sex-specific FH and 5–17 only after the 18+ diagnostics pass.

### Start here next session (handoff written 2026-10-24)

**Where things stand:** P3 passed its gate on 2026-10-24 (PR #1 merged). The public aggregates are in `data/public/aggregates/`: DHS 2024 by state and nationally, MPI 2021 by state and nationally on its own definitions, and GHS W4/W5 nationally and by zone. They are in dbt marts (`mart_prevalence_state`, `mart_prevalence_national_zone`), but **nothing is on the site yet**: `export_marts.py` doesn't export them. **P4 is next:** read `PLAN.md` → P4 and draft its detailed plan for the author, as was done for P3.

**Rules learned this session (keep them):**
- **Microdata never enters an LLM's context** (CLAUDE.md, two data zones). Print only metadata, counts with "<30" masking, or gated aggregates. Brief every subagent with this rule.
- **Nothing waits on outside replies.** The author works alone (memory `no-external-dependencies`). Outside input is optional; say so openly when that weakens a guarantee.
- The author is the statistician: there is no outside reviewer for the P5 pre-registration, so the OSF timestamp carries the credibility.

**P4 first steps:**
1. **The "first" check** (`PLAN.md` P4, item 7 below): do DHS 2024, MPI 2021 or DHS 2018 reports already publish disability prevalence by state? Record the answer in `verification.md` before any claim of "first".
2. **Design from the data we have:** DHS 2024 DISABILITY3 is the headline. 335 of the 518 DHS state cells are `review` (fewer than 10 events, or none), mostly single domains. Plan the Fay-Herriot small-area step and the hedged wording around this. The claim checker must treat `review` cells as hedged.
3. **The state pages** are designed from the profile list in `PLAN.md` P4 → "Light state pages". The user calls are optional (`docs/user-research.md`).
4. **`disability-access-charts` 0.2:** statistical findings and patterns (`PLAN.md` P4).
5. **The P4 map** goes through the chart library (Handoff notes → Maps).

**Obligations that start when figures go on the site (P4):**
- Send a PDF of each publication to references@dhsprogram.com (DHS).
- Send an electronic copy to the NBS National Data Archive (MPI).
- Done for the site as of 2026-10-30 (sent 2026-10-30, PDF of every page). Each later publication, including the P5 results, needs its own copy to both.
- Cite each dataset as the manifest says.

**Open decisions for the author:**
- **P5 exposure source:** MPI's non-WG measure misses people with difficulty who use no aid. The alternative is DHS 2024 with a global-MPI-style deprivation measure. Decide before the pre-registration (item 4a).
- **The P1 NVDA check:** still deferred; due before the P6 gate.
- **Outside people still named in the plan:** a Nigerian designer reviews the adire motifs (D31), and native-language reviewers check the P6 descriptions. Under the "nothing waits" rule, decide whether these become optional too.

**Regenerating the aggregates** (local only): `uv run python -I -m curbcut_ingest.aggregate`, after the harmonisers. Full steps are in `docs/reproduce.md`. Commit first, so that `script_commit` in the manifest names a real commit; otherwise it ends in `-dirty`.


1. ✅ Pushed and deployed 2026-10-17 (CI run 39004343042 green). **Author:** judge the look on the live page.
2. **Deferred (author, 2026-10-17): the NVDA part of the P1 gate.** The keyboard part passed a pre-check (see Done in P1). When picking it up, follow section 2 of `docs/accessibility-testing.md` on https://batestguy.github.io/curb-cut/ and listen for:
   - what NVDA says after "Show figures" (the heading "Lagos"? the "Showing 10 disability types…" message?);
   - the map's name on Tab, which should end "ranked 2 of 37", with the box not read a second time.

   Do it before the P6 gate at the latest. Automated Guidepup runs only work with every other window closed; the author's open apps took the keystrokes on 2026-10-17.

   **Partial run, 2026-10-27** (author, Brave, NVDA at the "Input/output" log level, so the log recorded every spoken phrase; Claude checked the log). The author moved through the page with Ctrl+Down and stopped before the state picker. Passed: the page title; "Skip to main content" is the first item; banner and main landmarks; headings h1 → h2 → h3 in a sensible order; each chart is read once as "figure, graphic" with its data description and no SVG noise; both tables give their caption and size, and each cell is read with its row and column headers ("Persons, column 2, 8,186,521"). Minor: the chart caption repeats the first sentence of the chart's description, and one Ctrl+Down step between the caption and the table was silent. **Not yet tested:** the state picker, Show figures and its spoken messages, the state card and the map. Next time, start at the "Tab to the state picker" step of section 2. To capture what NVDA says, set `loggingLevel = IO` under `[general]` in `%APPDATA%\nvda\nvda.ini`, and remove it afterwards (it logs every keystroke).
3. ✅ DHS 2024 downloaded and checked (see Done in P1). The data for P3/P4 is now complete: MPI 2021, DHS 2024, GHS W4/W5.
4. **P2 done (2026-10-22).** 0.1.0 is on PyPI. Gate: a fresh Python 3.12 venv installed `disability-access-charts[plotly]==0.1.0` from PyPI, ran all 3 examples (exit 0) and `check` passed both chart files; the tests mock the LLM. The root README now has the author's story, a hiring table and a diagram; CI enforces 85% coverage. P3 started 2026-10-24 (see item 4a).
   - Built: `bar()`/`dot()` documents, the claim checker (interval-aware, warnings for what it can't check), `audit()` with `chart-matches-data`, `theme()`, `to_html`/`to_csv`, `figure()`, the `check` CLI, the LLM gate (no errors or warnings except independence; `disclosure_checked=True` required), English templates, 3 examples. Dot plots set series side by side with whiskers in each series' colour. README shortened; full rules in `packages/disability-access-charts/docs/claim-checker.md`.
   - Verified: 379 pytest, ruff, pyright, pre-commit; dbt build, export, charts, map; site 18/18 Playwright + axe; clean wheel on 3.12 (core and `[plotly]`) and 3.10; the live `national_by_type` chart is byte-identical.
   - **0.1.1 follow-ups** (from the third review; all are false rejects or warnings, never silent passes): "the two highest" as a top-N rank; parenthetical and apposition lists ("12.0% (Kano)"); relative clauses ("…, which is higher than"); "50% higher" / "3 points higher" / "above 10%"; the audit could check `title` and trace `text` labels; a CI job on Python 3.10.
   - The original P2 brief follows for the record.
   - **What exists:**
     - `contrast.py` is the public API in 0.0.1 on PyPI: `contrast_ratio`, `passes_text` (SC 1.4.3), `passes_non_text` (SC 1.4.11), `relative_luminance`.
     - `experimental.py` is a stop-gap, not exported, not stable: `Theme` / `DEFAULT_THEMES`, `describe_bar_chart` (alt-text from the data), `check_alt_text`, `audit_chart` (contrast for every theme, including the highlight against the bars), and `bar_chart` (a JSON document with the Plotly spec, themes, alt-text, table, audit and meta, with no Plotly import).
     - The site's build (`packages/transform/scripts/build_charts.py`) depends on `experimental.bar_chart`.
   - **What P2 adds:**
     - modules: palettes, contrast, plots, `audit(fig)`, `theme()`, and the `disability-access-charts check` CLI;
     - outputs: checked alt-text, data-table export, keyboard metadata;
     - docs with three examples and a comparison with `maidr`;
     - publishing through the existing tag workflow (`charts-v<version>`).
   - **Gate:** a clean-environment install reproduces the examples, and the tests mock the LLM.
   - **Approach:**
     - Promote the proven parts of `experimental.py` into the 0.1 API rather than rewrite them.
     - Keep `experimental.bar_chart` working, or move `build_charts.py` to the new API in the same change, so CI and the live site never break.
     - The site's colour tokens must stay equal to the themes (see Handoff notes → Colour tokens).
     - Check that `maidr` and any new dependency are maintained before relying on them (CLAUDE.md rule).
     - LLM polish (Gemini → Groq) is optional. Every number it writes must be checked, results cached, no live calls in tests, and only public aggregates sent.
   - **Name and story:** keep `disability-access-charts`. The README and the PyPI `description` lead with "Built for Curb Cut, an accessible platform for Nigerian disability data", and `nigeria` goes in the keywords (`PLAN.md` P2).
   - **Out of scope for P2:** map or choropleth support. P4 decides how its prevalence map goes through the library (Handoff notes → Maps). The locator map's tip stays site code, since it is orientation, not a chart.
   - **Added 2026-10-21** (`PLAN.md` P2): the claim checker (extremes, pairwise, ratios, ranks, equality; interval-aware), uncertainty wording in generated alt-text, language-ready templates (English only), LLM polish gated on the claim checker, and the README led by "charts that check their own words". Example 2 is a dot plot with intervals showing one passing and one rejected claim.
   - **Carry-over follow-ups:**
   - Alt-text checks should also verify *which* category each number belongs to, not just that the number exists (review finding 8).
   - ✅ Done early (commit 36f5ca4): **"Show figures" button** instead of query-on-every-change (review finding 6). Still to check by ear at the P1 gate.
   - ✅ Done early (commit 36f5ca4, then the state card): focus moves to the result after "Show figures" (now the card's heading), so the load-finished state no longer depends on the live region alone. Still to check by ear.
4a. **P3 in progress (2026-10-24).** Plan agreed (`PLAN.md` → P3, steps 0–9); the author accepted every recommendation: GHS W3 dropped, headline 18+ with 5–17 separate, NCHS precision standard, first state aggregates committed but not on the site until P4.
   - ✅ Step 1: MPI routing checked (`verification.md` D43). Severity for seeing, hearing and walking was asked only after a "yes" screener and aid use, so **DHS 2024 is the main prevalence source**; MPI is labelled with its own definition.
   - **Open for P5 (not decided):** P5's exposure would come from MPI's non-WG measure, which misses people with difficulty who use no aid. Before the pre-registration, weigh using DHS 2024 with a global-MPI-style deprivation measure (OPHI's global MPI is built from DHS surveys) against MPI with its own definition.
   - ✅ Steps 2–8 built by `executor`, reviewed by `reviewer` (merge after fixes), fixes applied (2026-10-24):
     - Harmonisers (DHS 2024, MPI 2021, GHS W4/W5) → git-ignored `data/restricted/derived/`; R `survey` estimates (Korn–Graubard, checked against `svyciprop`); one disclosure gate; NCHS precision flag plus a project rule (fewer than 10 unweighted events → "review"; `n_events` never published); manifest.
     - Aggregates: `dhs2024_state` 518 rows (183 reliable, 335 review), `dhs2024_national` 90 (89/1), GHS W4 and W5 national/zone 13 each (all reliable); 0 suppressed (smallest DHS state denominator 799). MPI 532 rows (192 reliable, 340 review), released 2026-10-24.
     - dbt: metaplane `dbt_expectations` 0.10.10, prevalence marts, a fixtures target, 128 tests (129 on fixtures); `dbt docs` as a CI artifact. WorldPop committed (D44); Annex 3 state × sex seed. JONAPWD: 80/80 sampled cells match (150 of 370 checked overall). `docs/reproduce.md`.
     - Checks: ruff, pyright 0 errors, 427 pytest (94%), dbt, site 18/18, pre-commit.
   - ✅ Gate (2026-10-24): committed, manifest records clean commits, PR #1 CI green (R tests skip cleanly on the runner), merged by the author's go-ahead.
   - Not blocking, from the review: no numerator rule for disclosure (reasoning in `data/public/aggregates/README.md`: same as DHS and NCHS).
5. **P3–P5 follow-ups (2026-10-21):**
   - P3: a precision flag (RSE or interval width) with every aggregate; confirm the WG-SS DISABILITY3 cut-off against WG Doc 7A (`verification.md` D23).
   - **P3, optional (not blocking since 2026-10-24): user conversations.** Kit in `docs/user-research.md`. The author lines up 3–5 fifteen-minute calls (a disability organisation such as JONAPWD, a journalist, a researcher, a disabled user) and asks "What would you want to look up?". Notes go in `docs/user-research.md`. Also in P3: publish the aggregation scripts so anyone with their own NBS/DHS access can reproduce the figures.
   - P4: light pre-built state pages (one per state, plain HTML, no DuckDB-WASM; the full state profile from every public source), each with its own link and a build-time share image.
   - P4: 0.2 statistical findings (FDR-controlled, "N checked, K supported") and adire-inspired `patterns`; breakdowns by domain, severity, sex, age, urban/rural and wealth; AT unmet need only if rATA maps (D24); the disability-law panel from primary sources (D25).
   - P5: a methods-on-show page modelled on Ethnicity Facts and Figures (D32). The pre-registration also goes on OSF with a timestamp. No outside statistician (dropped 2026-10-24: the author is the statistician).
   - P6: a "report a problem" mailto link on every page; GoatCounter visit counts after checking its terms and adding a D-row.
6. **After P3, candidate: a `nigeria-states` package** (state-name matching, codes, zones, capitals, optionally boundaries). Recorded in `PLAN.md` → Candidates (not scheduled); it needs the author's go-ahead at the P3 gate.
7. **P4 follow-ups:**
   - **"First" check:** before claiming the first measured state figures, check whether the DHS 2024, MPI 2021 and DHS 2018 reports publish disability prevalence by state. Record the result in `docs/verification.md`. Launch copy (P7) relies only on what this check supports.
   - Methodology note explains the WG-SS cut-off vs the WHO 15%, so the comparison isn't framed as "JONAPWD was wrong" (see `PLAN.md` → Positioning).
   - Adopted into `PLAN.md` P4 → Spatial analysis (2026-10-17): spatial FH, Moran's I, LISA/clustering (exploratory), services-vs-needs correlation. The facilities source still needs a D-row in `verification.md` before use.
   - Disability NGO/OPD counts by state and type: no source exists (`verification.md` D15). Revisit only if JONAPWD or NCPWD shares a register.
8. **P6 follow-ups:**
   - **Added 2026-10-21:** descriptions in Hausa, Yoruba, Igbo and Pidgin, reviewed by the author's native reviewers, with a language selector and `lang` attributes, and an honest note that no screen-reader voice was found for them (D26, D27); test NVDA with `lang="yo"`. An adire-inspired decorative band reviewed by a Nigerian designer (D31). Font coverage check and a self-hosted woff2 subset (D29).
   - Pre-render the national table into the HTML at build time. First paint measured 4.8 s on the author's connection, against a 3 s target.
   - The charts show only 2–3 axis ticks at 320 px, and the 37-bar chart is cramped there ("Federal Capital Territory" takes half the width).
   - In light mode the highlighted bar's dark outline barely shows against its indigo fill (the bold label and colour still mark it). Try a lighter outline or a gap line. The Lagos ring doesn't cover the whole state at its western tip.
   - ✅ **Confirmed by the author (2026-10-24):** the 37 NBS Annex 3 state totals are now committed (seed `state_facts`) and published in `states.json`, and P3 added the state × sex split (74 figures, seed `state_population_by_sex_2023`). They are cited figures, not the file, but together they are the whole of an "All Rights Reserved" table.
   - `dist` is 74 MB (both DuckDB bundles), but each visitor downloads only one, about 8 MB gzip, and only after choosing a state.

## Handoff notes

- **Browser:** the author uses Brave with the Claude-in-Chrome extension connected ("Browser 1"). Use those tools in the author's logged-in session. A Brave launched by Playwright with its own profile does **not** share the author's logins. The author is logged in to PyPI, NBS microdata and the World Bank Microdata Library. Never type passwords; ask the author.
- **NBS portal quirk:** on access forms, the Submit button only enables after a real click on "I agree" (`isagree()`). Public-use requests are granted at once. Downloads land in `~/Downloads/Compressed/`.
- **Identity on applications:** Jerry Bannister, independent researcher, NBS account `jzbannister@atbu.edu.ng`. Gmail used for correspondence: batesthommie@gmail.com.
- **Local data** (git-ignored, never commit or send anywhere): `data/restricted/nbs-mpi-2021/` (MPI 2021 Stata files plus `MANIFEST.md`); `data/restricted/dhs-2024/` (DHS PR/HR recodes plus manifest); `data/restricted/ghs-w4/`, `data/restricted/ghs-w5/` (GHS-Panel Stata files plus manifests; the W4 disability file is `sect4a_harvestw4.dta`, the W5 one is `Post Planting Wave 5/Household/sect3_plantingw5.dta`); `data/sources/jonapwd/` (PDF); `data/sources/nbs-demographic-2023/` (xlsx).
- **State card data:** capitals, slogans and 2023 populations are in `packages/transform/seeds/state_facts.csv` (sources in `docs/verification.md` D12–D14, D16). Rule for slogans: keep one only where Zikoko and Wikipedia's list agree; otherwise leave it blank (the card omits the line). Populations were copied from the git-ignored NBS xlsx (Annex 3); there is no script for that, because the source file can't be in CI.
- **Data build order:** `dbt build` → `export_marts.py` → `build_charts.py` → `build_map.py` (the last needs only the committed GeoJSON and seeds). The map build's pytest lives in `packages/transform/tests_py/`, not dbt's `tests/`.
- **Maps (decided 2026-10-17):**
  - *Now:* the state card's locator map has no shading. JONAPWD counts would only show population (`verification.md` D17). The author turned down neighbour outlines, zone tint and a capital dot.
    - The card's JONAPWD row was removed (author, 2026-10-17). The figure ("N people: X% of the total for all 37 states, ranked Y of 37") now shows in a tip on the map: on hover (mouse, any state), on tap or click (any state), and on keyboard focus of the map (the chosen state, one Tab stop).
    - Esc closes the tip, and the pointer can move onto it (SC 1.4.13). Screen readers get the chosen state's figure in the map's accessible name; the tip is `aria-hidden`.
    - The "ranking mostly follows population" sentence went with the row; the page caveat still says the figures are 15% of population.
  - *P4:* measured prevalence by state, shaded, plus hotspot outlines (`PLAN.md` P4 → Spatial analysis). **Superseded 2026-10-28:** LISA found no hotspots, so the map has no outlines and says why (decisions log, 2026-10-28). This is a **separate national map**, in the P4 section, built from the same `build_map.py` paths so it looks the same. It shows data, so it goes through `disability-access-charts` (alt-text from the data, data table, audit); the locator doesn't. The locator stays in the card.
  - *Hover figures (P4):* allowed only as an extra. The same figures must also be reachable without a mouse, through the state picker, the card and the data table, and tapping a state on a phone must work too, since phones have no hover. A custom tooltip must meet WCAG 2.2 SC 1.4.13: it closes with Esc, the pointer can move onto it, and it stays until the pointer leaves. Don't make the 37 states separate Tab stops; the picker is the keyboard route.
- **Colour tokens:** the site's `--flag-green`/`--highlight` must stay equal to `DEFAULT_THEMES` mark/highlight in `palettes.py`; change both together and re-run the audit tests.
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
| 2026-10-17 | Positioning recorded in `PLAN.md` (gap analysis: assumed vs measured figures, what isn't new, one-line pitch). Any "first state figures" claim waits for the P4 check of the DHS/MPI reports. |
| 2026-10-17 | **Nigerian visual identity and state card built before the P1 gate**, at the author's request, so the gate tests the page that will stay. This pulls a little P6 polish and the geoBoundaries load (P3) forward. Choices: bold flag green; a green-white-green band, never a watermark behind text; a state card with a locator map, facts, slogan, and share and rank. All rules still hold (WCAG 2.2 AA in both modes, keyboard and NVDA, same origin, charts through `disability-access-charts`, every fact cited). |
| 2026-10-17 | **Spatial analysis added to P4, on measured prevalence (DHS 2024, MPI 2021) only:** spatial Fay-Herriot, Moran's I, LISA/clustering (exploratory), services-vs-needs correlation (ecological, descriptive). JONAPWD gets none: its state totals correlate 0.998 with population and its type shares are nearly constant (`verification.md` D17). Runs in P4; no code or dependencies before then. |
| 2026-10-17 | Locator map left as is until P4. P4 adds a separate national prevalence map with hotspot outlines and optional hover figures (see Handoff notes → Maps). Site tagline removed and the JONAPWD caveat shortened. |
| 2026-10-17 | **The author moved on to P2 with the NVDA part of the P1 gate deferred.** Keyboard pre-check passed on the live site; NVDA is to be done before the P6 gate at the latest. |
| 2026-10-17 | **The chart library keeps its generic name** (`disability-access-charts`), with the Nigeria story leading its README and PyPI description in P2. The Nigerian identity goes on genuinely Nigerian code: a `nigeria-states` package, recorded as a candidate after P3. |
| 2026-10-21 | **"Make it stand out" plan adopted** (package first, then the site; no new phase). The claim checker goes into 0.1; automatic findings go into 0.2 (P4). Native reviewers are available for Hausa, Yoruba, Igbo and Pidgin. Accepted for 0.1: the chart file only gains fields; bars with intervals show no value labels; each number must belong to the nearest category in its clause. Research logged as `verification.md` D18–D32 (several UNVERIFIED). |
| 2026-10-21 | **Audience ranked** (`PLAN.md` → Positioning): Nigerian users of the site first (advocates, policymakers, journalists, researchers, disabled Nigerians), recruiters second. The chart library serves anyone publishing charts. |
| 2026-10-21 | **Plan strengthened for the first audience** (`PLAN.md` P3–P6): user conversations before P4 is designed; light pre-built state pages with the full state profile (DuckDB-WASM only for the explorer); shareable state links and images; reproducible aggregation scripts; OSF pre-registration plus an outside statistician's read; a no-account "report a problem" link and GoatCounter counts. A minimum-launch cut was proposed and **declined: the author will do it all.** |
| 2026-10-24 | **P3 plan agreed** (`PLAN.md` → P3). GHS W3 dropped; headline age 18+ with 5–17 separate; NCHS proportion standards for the precision flag; first aggregates committed, shown from P4. MPI routing check (D43): **DHS 2024 becomes the main prevalence source**; MPI is never reported as DISABILITY3. |
| 2026-10-24 | **Don't wait for NBS.** The access terms already allow "reporting of aggregated information". DHS/GHS aggregates are pushed as planned; MPI aggregates are built locally but git-ignored until the P4 gate, and a follow-up to NBS gives 2026-11-30 as the earliest publication date. |
| 2026-10-24 | **No outside statistician:** the author (a statistician) does the statistical work and review. The pre-registration still goes on OSF with a timestamp before any outcome is examined. The NBS follow-up email is dropped; MPI aggregates stay held until the author decides at the P4 gate. User-call kit in `docs/user-research.md`. |
| 2026-10-24 | P3 goes to `main` through a PR (branch `p3-restricted-zone`). The MPI routing counts stay public in D43; the Annex 3 figures (37 totals + 74 by sex) stay committed as cited figures. |
| 2026-10-24 | **Nothing waits on outside replies** (author: "I am on my own, no one replies anything till we are done"). User calls become optional; the MPI hold is the author's own call at the P4 gate. The P6 requirement of feedback from a regular screen-reader user is still open: see Next actions. |
| 2026-10-24 | **P3 gate passed** (author): PR #1 merged. **MPI 2021 aggregates released** by the author without waiting for NBS (the access terms allow aggregated reporting; a copy of each publication still goes to the National Data Archive). **P6:** a regular screen-reader user's feedback is kept as a goal but no longer blocks the gate; the site says it hasn't been tested by one yet. |
| 2026-10-27 | **P4 pre-plan decisions** (author). (1) The "first" check: the author checks the NDHS 2024 final report (FR395) by hand, since the PDF is blocked to automated download; **Result (same day, `verification.md` D46): NDHS 2024 already publishes 15+ disability by state and sex, so no "first" claim**; the site leads with what is new (both sexes with intervals, domains at the WG cut-off, 5–17, small-area estimates, accessibility). Earlier web research found NDHS 2018 disability published by zone at most (Disability Data Initiative), and no state-level prevalence from DHS 2018, GHS or NBS (secondary sources only). (2) Spatial Fay-Herriot: `sae` 1.3 has a CRAN fix-by date of 2026-11-02, so `sae` and `spdep` (1.4-2) were added to `DESCRIPTION` and pinned in `renv.lock` now; plain FH remains the fallback. (3) MPI 2021 figures go on the site and state pages in P4, labelled as MPI's own non-WG measure and never the headline (DHS 2024 is). This settles the earlier MPI hold. (4) The law panel leaves out the count of states with their own law (17–26 depending on definition, press reports only); it keeps only primary-sourced facts. |
| 2026-10-27 | **P4 plan agreed** (author: "use all that will make this a top tier project"). Split into P4a (validate against the NDHS report, direct estimates, Fay-Herriot, spatial, map and comparison) and P4b (chart library 0.2, 37 state pages). FH: a pre-declared covariate set chosen by BIC (at most 2–3 for 37 states, since more would overfit), arcsine transform, smoothed variances, benchmarking, bootstrap MSE, published diagnostics; GRID3 facilities are not a covariate. Ages 5–17 by state only where precision or model diagnostics pass. |
| 2026-10-27 | **P4a step 0 passed.** Our pipeline reproduces every transcribed cell of NDHS 2024 Tables 14.1 and 14.2.x, and `svy` matches R on all 518 published state cells (D48). The site keeps the **de facto** population (as the report does). Our 18+ headline leaves out the 49 people whose age is unknown, and DISABILITY3 follows WG Doc 7A for "don't know" answers; both differences from the report are negligible and stated in the methodology note. `svy` 0.35.0 added to `curbcut-ingest`. The men's North East rows were added the same day; all 975 cells of Tables 14.2.x match. |
| 2026-10-27 | **Disclosure leak found and fixed** (review of P4a step 1; `verification.md` D49). Suppressed state × wealth cells could be approximated by subtraction. The author chose complementary suppression and a branch rewrite: `p4a-prevalence` was reset to 8df750e on GitHub within the hour and rebuilt without the leaky data commit (59e1e02), then force-pushed. GitHub may keep the old commit reachable by its hash until it is garbage-collected; it was never merged to `main`. |
| 2026-10-28 | **FH covariates approved and frozen** (all five, BIC rule). C4 changed to MICS women 15–49 (the 15–24 rate is national only; author chose it over the NDHS fallback, D53). Pre-fit technical corrections: GVF on log n, ML for BIC, an explicit failure rule. |
| 2026-10-28 | **FH result: direct estimates stay the headline** (author). No arcsine-normal model passes; FH would change estimates by ~4% (D56, reviewed). Published as a result; no amended model; spatial FH dropped. |
| 2026-10-28 | **Main page design (author):** measured prevalence leads (new H1), JONAPWD moves below as "what was assumed"; the comparison uses verified figures only (JONAPWD 15% assumed, NDHS 2024 15+: 15.5% any difficulty vs 2.8% at the WG cut-off, our DHS 18+ with CI, WHO's 16% quoted as WHO words it) and drops the spec's unsourced 10–18% grid; the map uses fixed rounded classes plus a dot chart of all 37 estimates with 95% intervals. No LISA hotspots, so no outlines; the map says so. |
| 2026-10-29 | **P4a gate passed** (author: "passed"). Evidence: CI, review fixes, the Guidepup NVDA transcript, and the author's own check of the state card with NVDA. PR #2 merged. |
| 2026-10-29 | **P4b plan agreed** (author: "yes"; `PLAN.md` steps 10–14). Map classes get pattern fills; the adire review is optional (D31); Claude pushes `charts-v0.2.0` after the author approves; AT unmet need deferred (D24). Step 10 done the same day: law facts from the gazetted Act (D25). It commenced on 17 January 2019, not on the 23rd; the 5% quota (s.29) covers public employers only, "as much as possible". |
| 2026-10-30 | **Accessible places per physically disabled person, by state: not built** (author asked to skip it if not feasible). OSM has 948 `wheelchair=*` tags in all of Nigeria, GRID3 has no accessibility attribute, and audits are local one-offs (D60). Out of scope until a national audit with state coverage is published. |
| 2026-10-30 | **P4b step 11 review fixes verified and committed** on `p4b-charts-pages`: ruff, pyright, 530 Python tests, dbt 208/208 (fixtures and real), `check --strict` on 4 charts, 38 site tests; the dot plot still reads "73 comparisons checked, 20 supported". |
| 2026-10-30 | **Before the 0.2.0 tag** (author: "proceed"): the claim checker never treats a pair with a zero-width interval as separated (it said "can show a difference" for any gap); the map's shade-only warning gets its own id, `shade-alone`, so `not-colour-alone` names one check. 531 Python tests; clean wheel installs on 3.12 and 3.10 pass. |
| 2026-10-30 | **P5 plan agreed** (author: "Do p5" and four choices, all as recommended; `PLAN.md` steps 15–21): treatment = any member 5+ with a severe difficulty on MPI's items; population-weighted ATE with EA clusters; GHS as an exploratory two-wave onset comparison; NBS Table 7 reproduced only after the OSF registration. The 71/62 figure is NBS's own (D61). |
| 2026-10-30 | **State pages: wealth shown by the state's zone first** (author: "keep zone first"); the state's own wealth cells, mostly review or unreliable, sit in a details element below. |
| 2026-10-30 | **P4b gate passed** (author: "pass"). Evidence: CI, review fixes, the Guidepup NVDA transcript of Edo and the main page, and the author's own check. PR #3 merged. D24 (AT unmet need) stays deferred to P5/P6. |
| 2026-10-30 | **`disability-access-charts` 0.2.0 released** (author: "yes edit and do it"): tag `charts-v0.2.0` pushed by Claude; PyPI trusted publishing passed; clean install from PyPI on 3.12 and 3.10 checked. |
| 2026-10-16 | **P0 gate passed.** Nigeria DHS 2024 is adopted as a second prevalence source next to MPI 2021. The exploratory panel uses GHS W4→W5 (all six WG-SS domains). |
| 2026-10-31 | **P5 exposure and analysis decisions** (author: "agree"): S2 "reading C" (NBS footnote 19); a household with a severe member is exposed whatever other members' missing answers; overlap population = mean unclipped propensity in [0.01, 0.99], always estimated; benchmark "place" = state + senatorial district; GHS work = wage, own farm, own business in both waves (W5 helping items dropped); GHS sample needs all six W4 domains; the executor's technical choices written into the pre-registration. |
| 2026-10-31 | **P5 pre-registration frozen** (author: "proceed" after the final read): revision 3, tag `p5-freeze` (22b8ace); section 11 filled; OSF registration next. Publication copies for the site as of 2026-10-30 sent to DHS and NBS (`Feedback@nigerianstat.gov.ng`, the catalogue's data-access contact). |
