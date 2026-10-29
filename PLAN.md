# Curb Cut: revised plan

Researched and agreed 2026-10-16. **This file is the source of truth.** `CurbCut.txt` is kept as the original spec for the record; where the two disagree, this file wins.

## Context

`CurbCut.txt` is a 12-week, 6-layer portfolio spec. This plan comes from a phase-by-phase critique of it, verification of its claims (free tiers and datasets especially), and a redesign aimed at recruiters for **any data role**.

About the author and setup:
- **Lived experience** with disability and assistive technology, which is front and centre.
- Working on this **full-time**, targeting **all job markets**.
- Claude writes the JS.
- Has a GitHub account and R installed. No data accounts and no PyPI account yet.

## What the research changed

### Spec claims

| Spec claim | Finding |
|---|---|
| JONAPWD PDF is extractable with pdfplumber | Planning research said the PDF had no text layer and needed OCR. **P0 found that wrong (2026-10-16):** it has a text layer, and pages 14–50 are per-state Power BI exports. Text extraction works, but the numbers come out sorted rather than next to their labels, so the mapping must be hand-validated. The "reliable data remains…" quote wasn't found outside the PDF itself. |
| HF `africa-disability-niger` = Nigerian disability data | It covers **Niger**. The `-nigeria` version is a WHO health-indicator mirror, not disability data. **Dropped.** |
| NBS MPI 2021, 144 disability variables | **Confirmed.** Covers the six Washington Group difficulty areas (seeing, hearing, walking, communicating, self-care, remembering), ages 5+, answered by a household member on others' behalf, with state/LGA IDs and free registration. **This is the main source.** |
| "71% vs 62% MPI poor" | **Not found.** We compute it ourselves from the microdata. |
| NPC 2025 state projections | Not public. Use the NBS Demographic Bulletin 2023 projections, with WorldPop (CC BY) as a cross-check. |
| Zenodo N. Nigeria PWD dataset | Not found. |
| Gemini 1,500 RPD / 1M TPM | Unsupported. Google publishes no numbers; third parties report about 100–1,000 RPD after cuts. Free-tier prompts may be used for training. Nigeria is supported. |
| Render cold start ~30 s | About **1 min**, out of 750 free hours per month. |
| HF Gradio/Docker Spaces need a paid plan | **Confirmed.** Static Spaces stay free. |
| Neon / Supabase / Codecov / PyPI OIDC / GH Actions / Pages limits | Confirmed. Pages allows 1 GB per site. Git warns on files over 50 MiB and rejects files over 100 MiB. |

### Corrections to earlier claims made during planning

| Earlier claim | Finding |
|---|---|
| `pymatchit-causal`, `StatsPAI` may not exist | Wrong: both exist and are active. Still not needed. |
| Publish data files as GitHub Release assets | Won't work: Release downloads lack CORS headers, so DuckDB-WASM can't read them. Host Parquet inside the Pages site instead. |
| `samplics` for survey statistics | Deprecated. Use `svy`, validated against R `survey`. |
| GHS-Panel onset design | National/zone-representative only. **P0 correction (2026-10-16):** the full WG-SS is in **W4 (2018/19) and W5 (2023/24)**, not W5 only; W3 asks only about seeing and walking. About 1,400 households appear in every wave. **Only an exploratory version is feasible**, but W4→W5 can cover all six domains. |
| Streamlit | Improving, but you can't control the page markup. Dropped. |

### New findings

- **DHS** registration was reported paused during planning. **As of 2026-10-16 it is open again**, and Nigeria DHS 2024 (with the full WG-SS) was released 2025-10-20. It is a candidate second prevalence source; deciding whether to use it is a P0 gate decision.
- **Licensing (NBS / World Bank / DHS):** household-level microdata may **not** be republished, including inside a dashboard. Only aggregates can be public.
- **Prior art:** `maidr` (Python accessible charts: keyboard, sound, braille, text) already exists. `a11yviz` (accessible plotnine/plotly/Quarto charts, WCAG 2.1, active since May 2026) also exists, so the planned name `a11y-viz` was unavailable: PyPI rejects names that match an existing project after removing `.-_` and mapping l/i→1, o→0. The library is renamed **`disability-access-charts`** and must stand apart from both maidr and a11yviz.
- **dbt:** pin dbt-core 1.x, since v2 is alpha. Use the metaplane fork of dbt-expectations.
- **Automated accessibility checks** catch only part of the problems: 57% in Deque's own vendor study, 20–30% of WCAG criteria in independent estimates. Manual testing by the author is a real differentiator.

## Decisions

- **Front end:** a static site with **DuckDB-WASM**. Parquet files sit inside GitHub Pages. Claude writes the JS.
- **disability-access-charts** stands apart from maidr through:
  - **alt-text checked against the data**
  - an accessibility **`audit()`** that can run in CI
  - a **data-table fallback** for every chart
- **LLM alt-text:** text built from the data is the default. The LLM (Gemini → Groq) is an optional polish step: its numbers are checked against the data, results are cached, and only public aggregates are ever sent.
- **Languages:** Python plus **R** for survey estimates, small-area estimation (`sae`/`emdi`) and DiD cross-checks (`did`).
- **API:** FastAPI on Render, **optional**. The site never depends on it.
- **Poverty analysis:**
  - **Primary:** NBS MPI 2021, pre-registered, adjusted association using DoubleML, with sensemakr / E-values.
  - **Secondary:** GHS W4→W5 onset event study (all six WG-SS domains), labelled exploratory and underpowered.
- **Population figures:** NBS 2023 bulletin, cross-checked against WorldPop.
- **P0 gate (2026-10-16):** Nigeria DHS 2024 is added as a second prevalence source (P3 load, P4 estimate side by side with MPI 2021). The exploratory panel uses GHS W4→W5.
- **Author's story:** front and centre, in a README section and a narrated NVDA/keyboard walkthrough video.
- **Stakeholder outreach:** later, once there's a demo.

## Positioning

Recorded 2026-10-17 from a gap analysis. These are findings from a search, not verified facts; P4 checks the "first" claim before anything public relies on it.

**Audience (decided 2026-10-21)**

1. **First: Nigerian users of the site.** Disability advocates and organisations (JONAPWD, NCPWD), policymakers, journalists, researchers, and disabled Nigerians themselves. When a choice trades polish for usefulness, they win: plain-language findings, Nigerian languages, phone-friendly pages, downloadable aggregates.
2. **Second: recruiters across data roles.** Real use by the first audience is the strongest portfolio evidence; the README's role table, the methods page and the claim checker serve them.

The chart library is a separate, generic audience: anyone publishing charts who needs them accessible and checked (newsrooms, statistics offices, NGOs, researchers). The installed package holds no data (one example in its source distribution uses JONAPWD's 10 cited national figures, labelled as assumed); people learn about disability in Nigeria from the site and its public data, never from microdata, which stays with NBS and DHS.

**The gap**

- **Assumed, not measured.** Nigeria's best-known disability figures (JONAPWD, ~35M people) come from multiplying the population by the WHO 15% benchmark. Measured Washington Group data (NBS MPI 2021, DHS 2018 and 2024) exists, but as far as the search found, only as national figures in PDF reports or locked inside licensed microdata.
- **No public state dashboard found.** The search found no public dashboard of measured state-level disability prevalence for Nigeria. Not found is not the same as doesn't exist (see the P4 check).
- **An untraced headline figure.** The "71% vs 62% MPI poor" figure circulates without a traceable source. Curb Cut computes it from the microdata.
- **Accessibility checked against the data.** Alt-text whose numbers are checked against the chart's data, a data table for every chart, and an audit that runs in CI.
- **Lived experience.** The author has lived experience of disability and assistive technology, and tests the site by keyboard and screen reader.
- **$0 and forkable.** Static site, public aggregates, MIT licence: anyone can fork it for another country with WG-SS data.

**What isn't new**

Survey-weighted estimation, Fay-Herriot small-area estimation, DoubleML with sensitivity analysis, and accessible charting (maidr, a11yviz) are all established. The novelty is combining them on Nigerian disability data, with the accessibility checks applied to the project's own output.

**One-line pitch:** Nigeria's disability numbers are mostly an assumption; Curb Cut puts measured, state-level survey estimates next to them, in charts that are checked against their own data.

**Pitch lines (added 2026-10-21):**
- *The package:* charts that check their own words. Every number, and every "higher", "largest", "twice" or "ranked 3rd", is checked against the data and its confidence intervals; LLM text is used only if it passes. A search found no other library that checks comparative claims against the data (closest: AggChecker, a VLDB 2019 research system; `docs/verification.md` D18). Say "we found no other", never "the first".
- *The site:* measured Nigerian disability figures, shown honestly with their uncertainty, in a visual language drawn from Nigerian textiles, with descriptions in Hausa, Yoruba, Igbo and Pidgin.

## Architecture: two data zones

Licensing makes this necessary.

- **Restricted zone (local only, git-ignored `data/restricted/`)**
  - Holds the NBS / GHS microdata.
  - R and Python scripts produce weighted aggregates from it.
  - A **disclosure check** suppresses cells with too few respondents (e.g. fewer than 30 unweighted).
  - Every output records its source, version, licence and suppression count in a manifest.
- **Public zone (in the repo)**
  - Holds the aggregate Parquet files.
  - The dbt project (dbt-duckdb 1.x) builds marts from those aggregates.
  - CI runs `dbt build` against **synthetic fixtures with the same schema**, so CI never touches restricted data.
  - Marts are exported to `site/data/*.parquet`.
- **Site:** semantic HTML, built with Vite.
  - Charts are rendered from **disability-access-charts JSON** produced at build time: the Plotly spec, alt-text, the data table and the audit result.
  - DuckDB-WASM handles interactive queries.
  - Pitch line: "disability-access-charts is under every chart" (Python at build time, Plotly.js at runtime).

## Recruiter tracks (README "Start here if you're hiring for…")

| Track | Showcase | 2-minute proof |
|---|---|---|
| Accessibility / frontend | disability-access-charts + site | axe/Lighthouse badge, NVDA walkthrough video, checked alt-text |
| Data / analytics engineering | Two data zones + dbt + PDF ingest | dbt docs, data tests, provenance manifest, measured extraction accuracy, disclosure control |
| Data science / statistics | Survey-weighted state prevalence + small-area estimation | Map of the JONAPWD 15% vs survey estimates with CIs, methodology note |
| Causal / econometrics | Pre-registered MPI analysis + exploratory panel | Pre-registration commit, DAG, sensitivity analysis, honest limits |
| Backend | FastAPI | OpenAPI docs, tests, rate limiting |
| Policy / communication | Brief + blog post + docs | PDF brief, a README you can grasp in 90 seconds |

## Phases

Full-time, about 11 weeks. **Every gate needs the author's review before the next phase starts.**

### P0 — Accounts, checks, bootstrap (days 1–4)
- **Accounts:**
  - Register on PyPI, NBS microdata and the World Bank Microdata Library (DHS optional, since it's paused).
  - Claim `disability-access-charts` on PyPI: a pending trusted publisher does **not** reserve a name, so the name is claimed by publishing a small real 0.0.1 (the WCAG contrast checker) from CI.
- **Before committing to the design:**
  - Is NBS MPI representative at state level? Check the sampling documentation.
  - Do the GHS W3/W4 questionnaires match W5's disability questions?
  - Read the NBS republication terms. Email NBS for written confirmation that aggregates can be published.
  - Download the JONAPWD PDF and check its licence notice.
  - Record the real Gemini and Groq quotas.
  - Confirm the WCAG 2.2 criteria wording (1.1.1, 1.4.3, 1.4.11, 2.1.1).
- **Repo setup:** a uv workspace with ruff, pyright and pytest, an R `renv` environment, pre-commit, and CI.
- **Gate:** CI green, and every check above written up in `docs/verification.md`.

### P1 — Thin vertical slice (weeks 1–2)
- Extract one JONAPWD table (text layer; no OCR needed) → dbt staging model → one mart → Parquet.
- A one-page site shows one chart from disability-access-charts JSON, plus the data table, with DuckDB-WASM.
- Playwright + axe run in CI; deploy to Pages.
- **Gate:** the live URL works by keyboard and with a screen reader (NVDA). The author checks it using `docs/accessibility-testing.md`.

### P2 — disability-access-charts 0.1 (weeks 2–4)
- **Modules:** palettes, contrast (1.4.3 / 1.4.11), plots, `audit(fig)`, `theme()`, and the `disability-access-charts check` CLI.
- **Outputs:** checked alt-text, data-table export, keyboard metadata.
- **Publishing:** docs with three examples, a comparison with maidr, and OIDC trusted publishing.
- **Name and story** (decided 2026-10-17): the name stays `disability-access-charts`, because the code is generic and a Nigerian name would oversell it and narrow its users. The README and the PyPI `description` lead with where it comes from: "Built for Curb Cut, an accessible platform for Nigerian disability data". Add `nigeria` to the keywords.
- **Claim checker** (added 2026-10-21): alongside the number-and-category check, `describe.py` checks extremes, pairwise comparisons, ratios (±5%), ranks and "the same as" against the data. With intervals, "A higher than B" passes only if abs(a−b) > 1.96·√(se_a²+se_b²) (se = half-width ÷ 1.96; assumes symmetric intervals and independent groups, with a warning when groups may not be independent). "No difference" always fails (suggest "the survey cannot show a difference"); an unsupported unqualified superlative fails; unrecognised comparatives give an "unchecked claim" warning. Generated alt-text uses uncertainty wording ("highest estimate", the interval, whether the survey can show a difference; summary first) and must pass its own checker. LLM polish must pass it too.
- **Language-ready templates:** sentence templates and claim vocabulary in one table per language, `describe(..., lang="en")`, category glossary, `alt_text_lang` in the chart file, numbers always as digits. Only `en` ships in 0.1.
- **README** leads with "charts that check their own words", honest about overlap with a11yviz (palettes, audits) and maidr (sound, braille, keyboard).
- **Gate:** clean-environment install reproduces the examples (example 2: a dot plot with intervals showing one claim that passes and one that is rejected); tests mock the LLM.

### P3 — Restricted zone + warehouse (weeks 4–6)
Detailed plan agreed 2026-10-24 (the author accepted every recommendation). Steps in order:

0. **Data-handling rule for every session and subagent:** microdata never enters an LLM's context. No `head()`, row prints or value dumps; scripts print only variable metadata, routing counts with cells under 30 shown as "<30", or aggregates that passed the disclosure check.
1. **MPI routing check (first; it decides MPI's role).** MPI 2021's disability module is not the standard WG-SS (`verification.md` D39): seeing, hearing and walking start with a yes/no screener, and the four-level question asks "even when wearing glasses / using a hearing aid / using equipment". A local script cross-tabulates screener against severity answers. **Decision:** if severity was asked of everyone, MPI is a second prevalence source next to DHS; if only after "yes", DHS 2024 is the main prevalence source and MPI is used for P5 (with its definition stated), not for headline prevalence. **Result (2026-10-24, D43): severity was asked only after a "yes" screener *and* aid use, so DHS 2024 is the main prevalence source.** MPI aggregates are still produced, but labelled with MPI's own (non-WG) definition, and never as DISABILITY3.
2. **Restricted ingest** (`packages/ingest`): one harmonisation module each for MPI 2021, DHS 2024, GHS W4 and W5. Each writes person-level Parquet to the git-ignored `data/restricted/derived/` with a common schema: state, zone, sector, sex, age band, weight, stratum, cluster, the six WG domains (1–4) and DISABILITY3. **GHS W3 is dropped** (not downloaded; seeing and walking only). GHS stays national/zone only.
3. **Aggregation, disclosure check, precision flag.** Weighted estimates with R `survey`. **One Python disclosure gate** that every output passes before it is written to `data/public/aggregates/`: cells with fewer than 30 unweighted respondents are suppressed and counted. **Precision flag:** the NCHS data presentation standards for proportions (Parker et al. 2017; effective sample size and interval width), not relative SE alone, which fails for small proportions (`verification.md` D42). The 30 rule protects privacy; it does not make an estimate reliable. A manifest entry per output: source, version, licence, file hash, script commit, suppression count. Tests use invented synthetic person rows only.
   - Design: DHS strata `hv023`, PSU `hv021`, weight `hv005`/10⁶. MPI has no strata variable: use senatorial district (`a1b`) × sector (`a3`) as strata and EA as PSU, recorded as an assumption (D40).
   - **Ages:** the headline figure is adults 18+; ages 5–17 are reported separately (both surveys ask from age 5).
4. **First public aggregates** (proves the pipeline end to end): DISABILITY3 and each domain by state × source, with SE, interval, unweighted n and precision flag. Committed, but not shown on the site until P4.
5. **Denominators:** extend the NBS Annex 3 seed to state × sex; cross-check WorldPop v3.0 (CC BY), with a D-row.
6. **Warehouse:** sources are the committed aggregates; alias seed; metaplane dbt-expectations (0.10.10, dbt ≥1.7 <3; DuckDB support to be tested, D41); tests for "no unsuppressed cell under 30", "every row has a precision flag", "all 37 states map"; synthetic fixtures for edge cases (suppressed cells, empty states); dbt docs built in CI.
7. **Measure extraction accuracy:** hand-check a random sample of JONAPWD state pages against the rendered PDF and report the accuracy in `data/public/jonapwd/README.md`.
8. **Reproducible from licensed data:** `docs/reproduce.md` and the published scripts take a researcher with their own NBS or DHS access from the raw `.dta` files to every published aggregate (the microdata never leaves `data/restricted/`).
9. **Bookkeeping:** D-rows, `CLAUDE.md` current state, CHANGELOG, README hero links.

Delegation: step 1 inline in the main session; steps 2–8 to `executor` (with the step 0 rule in its brief), then `reviewer`.
- **User conversations** (added 2026-10-21; **not blocking since 2026-10-24**: the author works alone and outside replies can't be counted on, so P4 is designed from the state-profile list below and any answers that do arrive refine it later): 15-minute calls with 3–5 people from the first audience (`Positioning` → Audience): someone from JONAPWD or another disability organisation, a journalist, a researcher, a disabled user. One question: "What would you want to look up?" Record the answers (no names without consent) in `docs/user-research.md`; they decide what the P4 state pages show.
- **Reproducible from licensed data:** publish the aggregation scripts so a researcher with their own NBS or DHS access can reproduce every published figure (the microdata never leaves `data/restricted/`).
- **Disability definition:** WG-SS DISABILITY3 (any domain "a lot of difficulty" or "cannot do at all"), confirmed against WG Doc 7A (`verification.md` D23). Headline 18+; ages 5–17 reported separately.
- **Gate:** `dbt build` green on the fixtures and the committed aggregates, and every public cell passes the disclosure check. The `nigeria-states` package decision is taken at this gate.

### P4 — Prevalence (weeks 6–7)
Detailed plan agreed 2026-10-27 (the author: "use all that will make this a top tier project"). P4 is split at a mid-point gate: **P4a** builds the numbers, the map and the comparison; **P4b** releases `disability-access-charts` 0.2 and builds the state pages. Nothing in the scope list below is cut. The step 0 data-handling rule from P3 applies to every session and subagent.

**Positioning (`verification.md` D46):** the NDHS 2024 report already publishes disability for adults 15+ by state, separately by sex, with no intervals. The site never claims the first state figures. What is new: both sexes together with intervals and a precision flag, each domain at the WG cut-off by state, ages 5–17, small-area estimates, spatial analysis, and an accessible, queryable presentation.

**P4a: numbers, map, comparison**
0. **Reproduce the published report first.** Re-run our pipeline on the report's definitions (de facto members, 15+, by sex × state, plus Table 14.1) and match Tables 14.1, 14.2.1 and 14.2.2 to the published decimal. Explain any difference before going on. Decide de facto vs de jure for the site (our 5+ count is about 148,100 against the report's 153,094) and record it. Cross-check the headline state estimates with Python `svy` (CLAUDE.md).
1. **Direct estimates.** By state: both sexes and each sex. 18+ headline, 5–17 separate. Breakdowns (domain, severity, sex, age band, urban/rural, wealth quintile) wherever the precision flag allows. Every figure carries its SE, interval, unweighted n and flag.
2. **Small-area estimates (Fay-Herriot).**
   - **Covariates:** a candidate set written down *before* any model is fitted, all state-level and public, each with a D-row: the share aged 60+ (age structure drives disability), urban share, MPI 2021 poverty headcount, female literacy or schooling, population density. GRID3 facilities are **not** a covariate, because step 3 tests them against need, and using them in the model would be circular. Selection by a pre-declared criterion (BIC), at most 2–3 covariates for 37 areas; the full candidate table and the choice are published.
   - **Model:** arcsine-transformed FH, standard for small proportions, with a bias-corrected back-transform. Sampling variances smoothed with a generalised variance function, because many state cells have few or no events. Estimates benchmarked so the states agree with the national direct estimate. MSE by parametric bootstrap.
   - **Spatial FH** (`sae::eblupSFH`, pinned, D47) compared with plain FH on MSE/CV. Check whether `emdi` (arcsine, benchmarking, bootstrap MSE) is fit for use before adding it; its maintainer email is reported undeliverable (D47).
   - **Diagnostics published:** residual normality, shrinkage per state, direct vs model estimates (they should agree where samples are large), and the CV gain. Where FH fails for a state, show the direct estimate with its CV.
   - **Outcome (2026-10-28, `verification.md` D56):** no pre-declared arcsine-normal model passed the diagnostics. The covariates explain too little to be selected, and the shrinkage factor γ ≈ 0.95 means FH gives only a negligible precision gain (median 4%). The author decided that **the direct estimates are the headline**: FH is published as a result, the spatial FH comparison is dropped, and the single-domain and 5–17 FH runs are not attempted. The rest of this step stays as written for the record.
   - **Coverage:** DISABILITY3 18+ first; single domains and 5–17 only if they have enough events and pass the diagnostics. Otherwise 5–17 stays at the levels where precision passes.
3. **Spatial analysis** as in the scope list below: queen contiguity from geoBoundaries, Moran's I per domain (permutation p), LISA with FDR control labelled exploratory, profile clustering, and services vs needs with GRID3 v2.0 (licence version confirmed on HDX first) labelled ecological.
4. **Data out.** `export_marts.py` exports the prevalence marts and the model outputs to `site/public/data/`; dbt tests extend to the new marts (every SAE row has an MSE; states sum to the national benchmark).
5. **Main page.** The prevalence map (through the chart library; hotspots carry a pattern or outline, never colour alone), the comparison (JONAPWD's 15%, our survey estimates, the NDHS report and the 10–18% grid), and the methodology note (WHO definitions checked against the reports themselves).
   - **Superseded (2026-10-28, `docs/STATUS.md` decisions log):** the unsourced 10–18% grid was dropped from the comparison, and the map has no hotspot outlines because LISA found no hotspots (D58); the page says so.
6. **P4a gate:** the map and comparison are live; CI green; the author's keyboard and NVDA check of the new section.

**P4b: chart library 0.2 and state pages**
7. **`disability-access-charts` 0.2:** statistical findings (FDR, "N checked, K supported"; findings from `review` cells hedged or suppressed), adire-inspired patterns, and map support. Published to PyPI the same way as 0.1.
8. **37 light state pages:** every public source for the state (DHS with intervals and the model estimate; MPI labelled as its own non-WG measure, never the headline; JONAPWD with its caveat; population; breakdowns), a share image, and the law panel with primary-sourced facts only (no count of states with their own law).
9. **P4b gate:** pages live; keyboard and NVDA check; then send the publication copies to DHS and NBS, and do the bookkeeping (D-rows, CLAUDE.md, CHANGELOG, README hero links).

**P4b detailed plan (agreed 2026-10-29; steps 10–14 expand steps 7–9 above).** Author decisions of 2026-10-29: the map gets pattern fills; the adire review (D31) is optional and not blocking; Claude pushes the `charts-v0.2.0` tag after the author approves; assistive-technology unmet need (D24) is deferred out of P4b.

- **10. Law facts first (main session).** Settle D25 from primary text before any page uses it:
  - **Done 2026-10-29 (D25):** the gazetted Act commenced on 17 January 2019; s.6 gives the five-year transition; s.29 sets the 5% quota for public employers only, "as much as possible"; s.31 establishes NCPWD. CRPD: signed 2007-03-30, ratified 2010-09-24.
  - The Act: find a primary copy (Official Gazette, National Assembly or NCPWD). Confirm the commencement date (sources say 17 or 23 January 2019), the section 6 five-year transition for public buildings (PLAC factsheet, July 2020), the exact wording and scope of the 5% employment provision (public employers only, or all?), and NCPWD's establishment (section 31).
  - No count of states with their own law.
  - Any fact without a primary source stays off the page.
- **11. `disability-access-charts` 0.2 (`executor`, then `reviewer`):**
  - *Statistical findings:* a `findings` block in the chart document. The families are pre-declared: extremes, gaps between groups, rankings and outliers. Every comparison is counted and the false discovery rate is controlled (Benjamini-Hochberg), and the block prints "N comparisons checked, K supported". Findings that touch `review` cells are hedged, and findings that touch suppressed cells are dropped. The claim checker and the audit cover the block.
  - *Patterns:* a `patterns` module of up to 5 abstract adire-inspired tiles drawn by us: rings and dots in the oniko style, checks and lines, never nsibidi or Ukara signs. Bars use Plotly `marker.pattern.path`; Plotly supports it on bar but not on scatter or choropleth (Plotly 7.1, checked 2026-10-29, D30). The map uses SVG `<pattern>` fills.
    - Colour and direct labels stay.
    - The audit checks that pattern and colour line up one to one, that the pattern ink has enough contrast against its fill in both themes, and that the legend shows each pattern.
    - Dot plots keep marker shapes.
  - *Map support:* `choropleth()` moves from experimental to the stable API, with patterns per class, docs and tests.
  - *Release prep:* bump to 0.2.0 and update the library README and CHANGELOG. Add a map example. Check a clean install of the built wheel on Python 3.12 (core and `[plotly]`) and 3.10.
  - *Site:* the main map uses the patterns, and the main page shows the findings block.
- **12. Release:** review, the author's go-ahead, then Claude pushes `charts-v0.2.0`. Trusted publishing does the rest. Then check a clean install from PyPI.
- **13. 37 state pages (`executor`, then `reviewer`):** built at build time as plain HTML at `site/states/<slug>.html`, with no DuckDB-WASM. A page should load in about a second on a phone, so each one gets a byte budget enforced by a test. Each page contains:
  - **DHS 2024:** the 18+ DISABILITY3 figure with its CI and flag, next to the national figure; both sexes and each sex; the six domains at the cut-off as a dot plot with intervals through the library; ages 5–17 where precision passes; urban/rural and wealth where the flag allows. Suppressed cells are named as "not shown: too few respondents".
  - **MPI 2021:** under its own non-WG definition, labelled as such, never the headline.
  - **JONAPWD:** the figure with its "assumed, not counted" caveat, and no spatial wording.
  - **Population:** NBS Annex 3 2023, by sex.
  - **Locator map.**
  - **Law panel:** national facts from step 10 only.
  - **Share image:** an Open Graph PNG made at build time by screenshotting a template with Playwright. Playwright is already a dev dependency, so nothing new is added. Its text is the same sentence as the page and its alt text, it passes contrast checks, and the meta tags use absolute URLs.
  - **Links in:** from the state card, the map table and a list of all 37 states.
  - **Tests:** all 37 pages build. Playwright + axe in light and dark on 3 states, including one with suppressed cells. One state's figures are hard-coded. The "first" check covers every page.
- **14. P4b gate:**
  - Pages are live and CI is green.
  - Keyboard + NVDA check: a scripted Guidepup transcript, plus the author's own check of whatever the script can't capture.
  - Then the author emails the publication copies: a PDF to references@dhsprogram.com (DHS), and an electronic copy to the NBS National Data Archive (MPI). Claude can prepare Gmail drafts.
  - Bookkeeping: D-rows (D25, D30, D31, D24 deferred), CLAUDE.md, CHANGELOG, README hero links.

Delegation: steps 0–2 inline in the main session (they need the author's judgement and touch restricted data through scripts only); steps 3–5 and 7–8 to `executor` with the step 0 rule in its brief, then `reviewer`.

**Scope reference** (agreed 2026-10-17 to 2026-10-21; the steps above implement it):
- Survey-weighted state prevalence by difficulty type and sex, with SEs (R `survey`, cross-checked with `svy`).
- Fay-Herriot small-area estimation for small-sample states.
- **Spatial analysis (on measured prevalence only)** (added 2026-10-17):
  - **Never on JONAPWD.** Its figures are 15% of population (r = 0.998 with NBS 2023 state population, checked 2026-10-17; `docs/verification.md` D17), so a spatial result would only reflect population. Say this in the methodology note.
  - **Spatial Fay-Herriot.** Small-area estimates where neighbouring states share strength through a spatial random effect, compared with the plain FH model by MSE/CV.
    - Neighbours: queen contiguity from the committed geoBoundaries file (`data/public/geoboundaries/`).
    - Candidate: `sae::eblupSFH`. Check that the package is maintained before adding it, and add it to `DESCRIPTION` Imports before `renv::snapshot()`.
    - If FH fails for a state, report the direct estimate with its CV.
  - **Moran's I.** One global test per difficulty domain, on the survey estimates, with a permutation p-value (e.g. `spdep::moran.mc`), against the same contiguity weights. Report it in words, e.g. "Difficulty seeing is / is not geographically clustered (I = …, p = …)".
  - **LISA hotspots and clustering: exploratory.**
    - LISA flags states that are high or low together with their neighbours. Correct for multiple comparisons and label results exploratory, since 37 units is few. Consider senatorial districts (MPI design: 3 per state, 109) if the district-level estimates are precise enough.
    - Cluster states by their profile across the six WG-SS domains (e.g. hierarchical clustering on standardised prevalences). This is descriptive only.
  - **Services against needs (descriptive, state level).**
    - Correlate measured prevalence with service supply per state: health facilities from GRID3 Nigeria, possibly schools or rehabilitation centres.
    - Label it an ecological association: no causal claim, no inference about individuals. P5's individual-level analysis is the rigorous version.
    - Before use, add a `docs/verification.md` D-row for the facilities source (licence, year, coverage).
  - **Accessibility.**
    - Every map result is also stated in a sentence and a table.
    - Hotspot and cluster maps use the existing pattern: `role="img"` with a data-derived name, the SVG hidden, and a data table.
    - Colour is never the only cue: add a pattern or outline for "hotspot".
    - Charts still go through `disability-access-charts`.
  - The P4 gate stays "the map and comparison are live". The spatial results go on the same page.
- Compare with the JONAPWD 15% figure and the 10–18% grid, plus the published DHS tables as a benchmark.
- **"First" check:** before any claim that these are the first measured state figures, check whether the DHS 2024, MPI 2021 and DHS 2018 reports publish disability prevalence by state. Record the result, with sources and date, in `docs/verification.md`. If any report does, the claim changes to what is actually new (e.g. accessible, queryable, with small-area estimates).
- Methodology note. It explains how the definitions differ: the WG-SS cut-off ("a lot of difficulty" or "cannot do at all" in at least one domain) is a narrower definition than the one behind the WHO 15%, a global estimate from different surveys and thresholds (check and cite the WHO source's definition when writing the note). Part of the gap between the survey estimates and JONAPWD comes from that difference, so the comparison is not framed as "JONAPWD was wrong".
- **`disability-access-charts` 0.2** (added 2026-10-21):
  - *Statistical findings:* pre-declared families (extremes, gaps, rankings, outliers); every comparison counted, false discovery rate controlled, "N comparisons checked, K supported" printed; findings from cells failing the disclosure or precision checks hedged or suppressed.
  - *Patterns:* a `patterns` module of up to 5 abstract adire-inspired tiles (oniko-style rings and dots, checks, lines) via Plotly `marker.pattern.path`, for grouped and stacked bars, always with colour and direct labels (SC 1.4.1); the audit checks that patterns and colours line up. Never nsibidi or Ukara signs. Test support beyond bar first (D30).
- **Breakdowns:** domain, severity, sex, age band, urban/rural and wealth quintile, by state where the precision flag allows. Assistive-technology unmet need (MPI `d22`–`d26`) only if WHO rATA's definitions map onto those questions (D24).
- **Light state pages** (added 2026-10-21): one page per state (37), built at build time as plain HTML text and small tables that load in about a second on a phone, with no DuckDB-WASM. Each is the state's profile: every public source for that state (JONAPWD, MPI, DHS estimates with intervals, population, breakdowns, the state's disability-law status). DuckDB-WASM stays for the P6 explorer only. GHS is national/zone only and never appears on a state page.
- **Shareable findings:** each state page has its own link and a small summary image made at build time (Open Graph), e.g. "Kano: X% of people have a disability (survey estimate)", with the same text in the page and the image's alt text. Images go through the same contrast checks.
- **"Nigeria's disability law" panel**, every fact from a primary source: the Act (signed 2019-01-23), the 5-year building transition (ended January 2024), the 5% jobs quota, NCPWD, the count of states with their own law, and the CRPD ratification year (D25).
- **Gate:** the map and comparison are live.

### P5 — Poverty analysis (weeks 7–9)
- **Pre-registration:** DAG, estimand and analysis plan committed *before* outcomes are examined.
  - Also registered on OSF (free) for a public timestamp (added 2026-10-21).
  - ~~An outside statistician reads it first~~ Dropped 2026-10-24: the author is the statistician. The OSF timestamp before any outcome is examined carries the credibility; an outside read is welcome but optional.
- **Primary (MPI):**
  - Estimate the poverty gap between households with and without a disabled member using DoubleML, controlling for confounders, with SEs.
  - Robustness: sensemakr / E-values, a placebo treatment, DoWhy refutations.
  - Reported as an **adjusted association**, not a causal effect.
- **Exploratory (GHS):** event study on onset of difficulty between W4 and W5 (all six WG-SS domains; W3 dropped on 2026-10-24), using pyfixest checked against R `did`, with power stated honestly.
- **Brief:** policy brief written via pandoc.
- **Methods on show** (added 2026-10-21): the results page explains, with worked examples, survey weights, intervals, adjusted association versus effect, and sensitivity analysis, modelled on the UK Ethnicity Facts and Figures "how to read survey data" page (D32).
- **Gate:** the brief is committed and the results page is live.

### P6 — API + site polish (weeks 9–10)
- **API:** FastAPI on Render, reading the public Parquet.
  - Endpoints: `/states`, `/prevalence`, `/compare`, `/poverty`, `/status`.
  - Rate limiting; its docs page notes the cold start.
- **Site:**
  - Pages: explorer, sensitivity slider, poverty, methodology, data dictionary.
  - CSV/JSON downloads everywhere; Lighthouse CI.
- **Feedback and use** (added 2026-10-21):
  - A "report a problem" link on every page that needs no GitHub account (a mailto link), reachable by keyboard.
  - Visit counts with GoatCounter (free for non-commercial use, no cookies), so launch copy can say how many people used it. A third-party service: check its terms, data handling and that the script passes axe before adding it, and record a `verification.md` D-row. It never receives anything but page views.
- **Languages** (added 2026-10-21): chart descriptions in Hausa, Yoruba, Igbo and Pidgin (templates and glossaries translated, reusing NCPWD's Disability Act terms, D26), reviewed by the author's native reviewers. A language selector with `lang` attributes (`ha`, `yo`, `ig`, `pcm`). Say on the page that no screen-reader voice was found for these languages (D27), so the descriptions serve readers, not listeners; test by hand what NVDA does with `lang="yo"`.
- **Look:** an adire-inspired decorative band (`aria-hidden`, at least 3:1 in both themes) next to the flag band, reviewed by a Nigerian designer or textile practitioner before launch (D31).
- **Type:** check that Atkinson Hyperlegible Next or Noto Sans covers ẹ̀ ọ́ ṣ ɓ ɗ ƙ ƴ ị ụ ṅ (fontTools plus a browser render, D29); self-host a woff2 subset and record its size.
- **Gate:** accessibility score 100 in CI, the walkthrough video recorded, and the author's keyboard + NVDA check. **Feedback from a regular screen-reader user is sought but not blocking** (author, 2026-10-24): until it arrives, the site states that it hasn't yet been tested by a regular screen-reader user and offers a "report a problem" link; feedback is acted on when it comes.

### P7 — Launch (weeks 10–11)
- README with the role table, the author's story, a Mermaid diagram and a GIF.
- MkDocs, Zenodo DOI, CONTRIBUTING and CHANGELOG.
- **Blog posts:**
  - "Alt-text that can't lie"
  - "Nigeria's disability numbers are an assumption — here's what surveys say"
- **Launch copy** (README, posts, outreach) uses only claims backed by the P4 "first" check in `docs/verification.md`.
- Optional: reach out to JONAPWD/NCPWD with the demo.

## Candidates (not scheduled)

Ideas the author wants kept, outside the fixed phase order. Each needs the author's go-ahead at a gate before any work.

- **`nigeria-states` package (after P3, recorded 2026-10-17).** A small published Python package for the Nigeria-specific plumbing that every Nigerian data analyst repeats:
  - state-name matching across spellings (the P3 alias seed: "FCT"/"Abuja", "Nassarawa"/"Nasarawa", "Akwa-Ibom"…);
  - ISO 3166-2 codes, geopolitical zones and capitals, each with its source (`docs/verification.md` D12, D16);
  - optionally, the geoBoundaries ADM1 shapes (CC BY 4.0, attribution kept).

  Why: it is genuinely Nigerian code with a Nigerian name, a local problem solved in package form, which matters to recruiters in and out of Nigeria. The chart library stays generic. Wait until P3, when the alias seed is complete and tested. Before starting:
  - check the name on PyPI and look for existing packages that do this, and record the result in `verification.md`;
  - confirm every bundled fact's licence (the NBS Annex 3 populations are "All Rights Reserved" and stay out).

## Cut from the spec

The HF dataset, conda-forge, Streamlit, committing the DuckDB file, the Monte Carlo with `random()`, the 4-library causal stack, Neon/Supabase, and the unverified "71/62%" figure.

## Verification

- `docs/verification.md` records each P0 check with its source URL and date.
- Per-gate checks:
  - CI green: ruff, pyright, pytest, `dbt build` on fixtures, axe and Lighthouse
  - the disclosure check passes on every public Parquet file
  - the live site loads in under 3 s with no backend
  - `pip install disability-access-charts` works in a fresh venv
  - the author completes the keyboard and NVDA script (`docs/accessibility-testing.md`) at each site gate, and the site states honestly whether a regular screen-reader user has tested it yet
