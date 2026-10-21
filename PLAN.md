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

The chart library is a separate, generic audience: anyone publishing charts who needs them accessible and checked (newsrooms, statistics offices, NGOs, researchers). It holds no Nigerian data; people learn about disability in Nigeria from the site and its public data, never from microdata, which stays with NBS and DHS.

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
- Load MPI 2021, GHS W3–W5, NBS 2023 projections, WorldPop and geoBoundaries (CC BY).
- **Measure extraction accuracy:** hand-check a sample of the JONAPWD state pages against the rendered charts and report the accuracy.
- **Warehouse:** alias seed, manifest, dbt tests with metaplane dbt-expectations, synthetic fixtures, dbt docs.
- **Precision flag** (added 2026-10-21): keep the ≥30-respondent disclosure rule and also store a precision flag (relative standard error or interval width) with every aggregate. The 30 rule protects privacy; it does not make an estimate reliable.
- **Disability definition:** WG-SS DISABILITY3 (any domain "a lot of difficulty" or "cannot do at all"); ages 5–17 reported separately. Confirm against WG Doc 7A first (`verification.md` D23).
- **Gate:** `dbt build` green on the fixtures, and the public aggregates pass the disclosure check.

### P4 — Prevalence (weeks 6–7)
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
- **"Nigeria's disability law" panel**, every fact from a primary source: the Act (signed 2019-01-23), the 5-year building transition (ended January 2024), the 5% jobs quota, NCPWD, the count of states with their own law, and the CRPD ratification year (D25).
- **Gate:** the map and comparison are live.

### P5 — Poverty analysis (weeks 7–9)
- **Pre-registration:** DAG, estimand and analysis plan committed *before* outcomes are examined.
- **Primary (MPI):**
  - Estimate the poverty gap between households with and without a disabled member using DoubleML, controlling for confounders, with SEs.
  - Robustness: sensemakr / E-values, a placebo treatment, DoWhy refutations.
  - Reported as an **adjusted association**, not a causal effect.
- **Exploratory (GHS):** event study on onset of difficulty between W4 and W5 (all six WG-SS domains; W3→W5 for seeing/walking only), using pyfixest checked against R `did`, with power stated honestly.
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
- **Languages** (added 2026-10-21): chart descriptions in Hausa, Yoruba, Igbo and Pidgin (templates and glossaries translated, reusing NCPWD's Disability Act terms, D26), reviewed by the author's native reviewers. A language selector with `lang` attributes (`ha`, `yo`, `ig`, `pcm`). Say on the page that no screen-reader voice was found for these languages (D27), so the descriptions serve readers, not listeners; test by hand what NVDA does with `lang="yo"`.
- **Look:** an adire-inspired decorative band (`aria-hidden`, at least 3:1 in both themes) next to the flag band, reviewed by a Nigerian designer or textile practitioner before launch (D31).
- **Type:** check that Atkinson Hyperlegible Next or Noto Sans covers ẹ̀ ọ́ ṣ ɓ ɗ ƙ ƴ ị ụ ṅ (fontTools plus a browser render, D29); self-host a woff2 subset and record its size.
- **Gate:** accessibility score 100 in CI, the walkthrough video recorded, and **feedback from at least one regular screen-reader user collected and acted on**. Start looking for that tester (JONAPWD, a blind persons' association, NVDA user communities) during P4–P5, so the feedback lands before launch.

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
  - the author completes the keyboard and NVDA script (`docs/accessibility-testing.md`) at each site gate, and a regular screen-reader user's feedback is in before launch
