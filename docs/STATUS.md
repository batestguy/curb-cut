# Status and handoff

The one page to read first. It says where things stand and what happens next. The rules live in `CLAUDE.md`, the roadmap in `PLAN.md`, and the P0 evidence in `docs/verification.md`. Update this page at every working session and every gate.

**Last updated:** 2026-10-22 · **Current phase:** P2 built, awaiting the author's gate review. `disability-access-charts` 0.1.0 is committed but **not published**: publishing to PyPI needs the author's go-ahead (a version can't be reused). P1 is live; its NVDA check is deferred.

## Phases

| Phase | State | Gate |
|---|---|---|
| P0 Accounts, checks, bootstrap | ✅ done 2026-10-16 (author sign-off) | CI green ✅ · checks confirmed or decided ✅ · author review ✅ |
| P1 Thin vertical slice | 🟡 built and live; keyboard pre-check passed 2026-10-17. **The author's NVDA check is deferred (author, 2026-10-17)**: do it before the P6 gate at the latest | Live URL works by keyboard and with NVDA (author, per `docs/accessibility-testing.md`) |
| P2 disability-access-charts 0.1 | 🟡 built 2026-10-22 (executor, three reviewer rounds, final fixes inline); not yet published | Clean install reproduces examples; LLM mocked in tests |
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
| NBS reply on publishing aggregates | NBS | 2026-10-16 |
| Gemini / Groq real quotas | Accounts (P2) | 2026-10-16 |

## Next actions (pick up here)

1. ✅ Pushed and deployed 2026-10-17 (CI run 39004343042 green). **Author:** judge the look on the live page.
2. **Deferred (author, 2026-10-17): the NVDA part of the P1 gate.** The keyboard part passed a pre-check (see Done in P1). When picking it up, follow section 2 of `docs/accessibility-testing.md` on https://batestguy.github.io/curb-cut/ and listen for:
   - what NVDA says after "Show figures" (the heading "Lagos"? the "Showing 10 disability types…" message?);
   - the map's name on Tab, which should end "ranked 2 of 37", with the box not read a second time.

   Do it before the P6 gate at the latest. Automated Guidepup runs only work with every other window closed; the author's open apps took the keystrokes on 2026-10-17.
3. ✅ DHS 2024 downloaded and checked (see Done in P1). The data for P3/P4 is now complete: MPI 2021, DHS 2024, GHS W4/W5.
4. **P2 (built 2026-10-22, awaiting the author's gate review).**
   - **Author:** review the gate (clean install reproduces the examples; tests mock the LLM) and decide on publishing: bump nothing, push tag `charts-v0.1.0`, and trusted publishing does the rest.
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
5. **P3–P5 follow-ups (2026-10-21):**
   - P3: a precision flag (RSE or interval width) with every aggregate; confirm the WG-SS DISABILITY3 cut-off against WG Doc 7A (`verification.md` D23).
   - **P3, before P4 is designed: user conversations.** The author lines up 3–5 fifteen-minute calls (a disability organisation such as JONAPWD, a journalist, a researcher, a disabled user) and asks "What would you want to look up?". Notes go in `docs/user-research.md`. Also in P3: publish the aggregation scripts so anyone with their own NBS/DHS access can reproduce the figures.
   - P4: light pre-built state pages (one per state, plain HTML, no DuckDB-WASM; the full state profile from every public source), each with its own link and a build-time share image.
   - P4: 0.2 statistical findings (FDR-controlled, "N checked, K supported") and adire-inspired `patterns`; breakdowns by domain, severity, sex, age, urban/rural and wealth; AT unmet need only if rATA maps (D24); the disability-law panel from primary sources (D25).
   - P5: a methods-on-show page modelled on Ethnicity Facts and Figures (D32). The pre-registration also goes on OSF, and an outside statistician (ideally at a Nigerian university) reads it before any outcome is examined: **the author should start looking for that reader during P3–P4.**
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
   - **Author to confirm:** the 37 NBS Annex 3 state totals are now committed (seed `state_facts`) and published in `states.json`. They are cited figures, not the file, but they are the whole total column of an "All Rights Reserved" table.
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
  - *P4:* measured prevalence by state, shaded, plus hotspot outlines (`PLAN.md` P4 → Spatial analysis). This is a **separate national map**, in the P4 section, built from the same `build_map.py` paths so it looks the same. It shows data, so it goes through `disability-access-charts` (alt-text from the data, data table, audit); the locator doesn't. The locator stays in the card.
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
| 2026-10-16 | **P0 gate passed.** Nigeria DHS 2024 is adopted as a second prevalence source next to MPI 2021. The exploratory panel uses GHS W4→W5 (all six WG-SS domains). |
