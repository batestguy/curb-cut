# Publication readiness

Written 2026-11-04 on branch `academic-polish` (an author-approved detour from P6). It records what the repository already holds for three possible papers, and what a Q1 journal reviewer would still ask for. It was assembled from the committed public files and documents only; nothing under `data/restricted/` was read. Citation keys refer to `docs/references.bib`. No manuscript exists yet; section 9 is where the author chooses whether to draft one.

File references are `path:line` on this branch. In the library sections (1.2, 2.4, 3.2, 6.2 and the library rows of section 8), the paths `README.md`, `LICENSE`, `pyproject.toml`, `docs/claim-checker.md`, `docs/findings.md`, `docs/maps.md`, `docs/patterns.md`, `src/`, `tests/` and `examples/` mean the files under `packages/disability-access-charts/`; every other path is from the repository root.

Three papers are in view:

- **Paper 1 (empirical):** disability in the household and multidimensional poverty in Nigeria; NBS MPI Survey 2021; pre-registered (OSF https://osf.io/kes3p/); DoubleML adjusted association; exploratory GHS-Panel two-wave comparison.
- **Paper 2 (methods/data):** state disability prevalence from Nigeria DHS 2024 (WG-SS), with disclosure-gated open aggregates, an NCHS precision flag, reproduction of the published report tables, and a Fay-Herriot attempt that was not used.
- **Paper 3 (software):** `disability-access-charts` 0.3.0 (`packages/disability-access-charts/`).

## 1. Candidate venues

### 1.1 Papers 1 and 2

Scope was checked against each journal's stated aims. SCImago (scimagojr.com) refused scripted access on 2026-11-04 (Cloudflare challenge), so no quartile below was read from SCImago itself. Where third-party aggregators of SJR agree, that is said; otherwise "Q1 status not confirmed". Check each on scimagojr.com before submission.

| Paper | Venue | Why it fits | Q1 status |
|---|---|---|---|
| 1 | *World Development* (Elsevier) | Poverty and development in low- and middle-income countries; publishes survey-based observational analyses | Q1 per SJR aggregators (Development; Economics and Econometrics); not confirmed on SCImago |
| 1 | *Social Science & Medicine* (Elsevier) | Social determinants of health and disability; accepts adjusted-association designs with sensitivity analysis | Q1 per an SJR aggregator (2024 SJR 2.103; Health (social science)); not confirmed on SCImago |
| 1 | *Disability and Health Journal* (Elsevier) | Disability-specific; publishes population surveys on disability and poverty | Q1 per aggregators (Public Health, Environmental and Occupational Health); not confirmed on SCImago |
| 1 (alt.) | *Journal of Development Studies* (Taylor & Francis) | Development economics with applied micro methods | Q1 status not confirmed |
| 2 | *Scientific Data* (Nature Portfolio) | Data Descriptors with technical validation: fits the open aggregates, the reproduction of FR395 (D48) and the disclosure gate | Q1 status not confirmed |
| 2 | *Population Health Metrics* (BMC) | Measurement of population health, including subnational estimation and small-area methods | Q1 status not confirmed (Peeref gives a CiteScore Q2 in Public Health) |
| 2 (alt.) | *Disability and Health Journal* | Prevalence of disability by subnational area with the WG-SS | As above |

A methods-only angle on the disclosure gate and precision flag (a short note) could go to the *Journal of Survey Statistics and Methodology*; Q1 status not confirmed.

### 1.2 Paper 3

| Venue | Type | Fit | Indexing / ranking | Main obstacle now |
|---|---|---|---|---|
| **Journal of Open Source Software (JOSS)** | Journal, open review on GitHub, short `paper.md` plus the software | Best fit: reviews the software itself, not a study | Papers get a Crossref DOI (`JOSS2026Submitting`). JOSS's own pages say nothing about Scopus, Web of Science or quartiles; it is **not a Q1 journal in the usual (JCR / SJR) sense** and should not be presented as one | Development history (section 2.4, item 10): commits on the library start 2026-10-16, about three weeks ago; JOSS asks for an extended public history, preferably 6 months or more, and treats work concentrated just before submission as unacceptable |
| **ACM ASSETS** (International ACM SIGACCESS Conference on Computers and Accessibility) | Peer-reviewed conference (full papers, short papers / posters, demos) | Good fit for an accessibility contribution, but expects an evaluation with disabled users; a demo or poster is the realistic first step | A conference: journal quartiles do not apply | Needs a study with screen-reader users (section 3.2.1) |
| **IEEE VIS short papers** (published in IEEE TVCG's proceedings track or IEEE Xplore) / **IEEE TVCG** | Conference / journal | Fits the visualisation side (claim checking of chart text, colour-vision screening, FDR-controlled findings) | TVCG is widely reported as Q1; **not confirmed here** (SCImago returned 403 to an automated check) — TODO(verify) | Needs a novel contribution beyond engineering, plus an evaluation (accuracy of the claim checker on a corpus, and a user study) |
| ACM TACCESS (Transactions on Accessible Computing) | Journal | Fits a fuller paper with a user evaluation | A secondary aggregator lists it as Q2 (JCR and SJR); **not confirmed** — TODO(verify) | Same evaluation gap as ASSETS |
| Computer Graphics Forum (EuroVis short papers) | Journal / conference | Possible for the colour and map work | Quartile **not confirmed** — TODO(verify) | Novelty of the map rules is modest on its own |

Recommendation: JOSS first, once the development-history condition can be met (about 2027-04 at the earliest, six months after the first commit), with an ASSETS poster or demo, or a VIS short paper, when a screen-reader user study and a claim-checker accuracy study exist. Do not describe JOSS as Q1.

## 2. Reporting checklists

Status: **met** (the repository has it), **partly** (present but incomplete, or only on the site), **missing**. "Manuscript" means the item belongs in a paper that does not yet exist; the repository holds the material for it.

### 2.1 Paper 1: STROBE, cross-sectional (von Elm et al., 2007, `vonElm2007STROBE`)

| # | Item | Status | Evidence / what is missing |
|---|---|---|---|
| 1a | Design in title or abstract | partly | `docs/osf-registration.md` TITLE and DESCRIPTION say "pre-registered secondary analysis"; no manuscript abstract yet |
| 1b | Informative, balanced abstract | missing | Manuscript |
| 2 | Background and rationale | partly | `docs/preregistration.md:14-16`, `:42-43` (NBS Table 7); no literature review of disability–poverty studies in Nigeria or sub-Saharan Africa anywhere in the repo |
| 3 | Objectives, pre-specified hypotheses | met | `docs/preregistration.md:14-28` (Q1, S1–S6, X1, E1; two-sided test) |
| 4 | Study design early in the paper | met | `docs/preregistration.md:10`, `:16`, `:123` |
| 5 | Setting, dates, data collection | partly | Fieldwork 2021–22 at `docs/preregistration.md:34`; sampling (102 EAs per state) only in `docs/verification.md:62` (D40) and `:24` (D1); no description of the survey's fieldwork months in the plan |
| 6a | Eligibility, sources, selection | met | `docs/preregistration.md:58-61` |
| 7 | Outcomes, exposure, confounders defined | met | `docs/preregistration.md:63-103`; MPI indicators at `docs/verification.md:86` (D64) |
| 8 | Data sources and measurement, comparability | met | `docs/verification.md:61`, `:65` (D39, D43: MPI items are not the WG-SS; routing) |
| 9 | Efforts to address bias | met | DAG `docs/preregistration.md:105-123`; misclassification `:69`; sensitivity `:152-159`; refutations `:161-168` |
| 10 | Study size | partly | 51,422 households analysed, 680 exposed (`data/public/aggregates/p5_mpi_estimates.csv`, row `primary`); no a-priori precision calculation for the MPI analysis (one exists for GHS, `docs/preregistration.md:208`) |
| 11 | Handling of quantitative variables | met | Head's age as a spline, counts as given (`docs/preregistration.md:139`) |
| 12a | Statistical methods incl. confounding | met | `docs/preregistration.md:133-146` |
| 12b | Subgroups and interactions | partly | X1 is descriptive (`:27`, `:172`); no interaction test is pre-specified, yet the urban (29.4 points) and rural (6.7 points) X1 estimates differ widely (`p5_mpi_estimates.csv`, `x1_sector_*`) |
| 12c | Missing data | met | `docs/preregistration.md:185-189`; counts in `p5_mpi_summary.csv` (`missing_*`) |
| 12d | Sampling strategy in the analysis | partly | Weights in the score, EA clusters without strata (`docs/preregistration.md:61`, `:135`); the strata are an assumption (`docs/verification.md:62`, D40) |
| 12e | Sensitivity analyses | met | `docs/preregistration.md:152-168` |
| 13a | Numbers at each stage | partly | `p5_mpi_summary.csv` (households in sample 52,022; poverty missing 545; exposure missing 59; analysed 51,422) |
| 13b | Reasons for non-participation | partly | Survey response 91.9% in `docs/verification.md:23` (D1) and `:63` (D40), which disagree on the interviewed count (52,022 vs 53,415); not in the plan or brief |
| 13c | Flow diagram | missing | Manuscript; numbers exist |
| 14a | Characteristics by exposure | **missing** | No published table of confounders by exposure; it can be produced through the disclosure gate (weighted shares only) |
| 14b | Missing data per variable | partly | Only for exposure and outcome |
| 15 | Outcome numbers | partly | NBS-definition poverty shares (Table 7 check: 72.0% vs 61.8%, `p5_mpi_summary.csv` `table7_*`); no unadjusted poverty share under the **primary** exposure definition |
| 16a | Unadjusted and adjusted estimates with precision | partly | Adjusted primary with 95% CI (`p5_mpi_estimates.csv` `primary`: 0.117, 0.061 to 0.172); the unadjusted gap is published only for the S2 definition |
| 16b | Category boundaries | met | `docs/preregistration.md:95` (age bands) |
| 16c | Absolute risk translated | met | Risk difference is the primary scale; risk ratio 1.19 (`p5_mpi_summary.csv` `evalue_rr`) |
| 17 | Other analyses | met | S1–S6, robustness, leave-one-zone-out, X1, sensemakr in `p5_mpi_estimates.csv` |
| 18 | Key results | partly | Brief and results page; manuscript |
| 19 | Limitations | met | `docs/preregistration.md:69`, `:99`, `:103`, `:123`; `docs/brief/p5-poverty-brief.md:20-34` |
| 20 | Cautious interpretation | met | `docs/preregistration.md:191-197`; wording guard `packages/transform/scripts/poverty_text.py:38-45` |
| 21 | Generalisability | missing | No discussion of what the 2021–22 estimate says beyond the MPI survey population, nor of comparability with other countries' WG-based studies |
| 22 | Funding and role of funders | missing | No funding or competing-interests statement anywhere |

### 2.2 Pre-registration transparency (paper 1)

| Item | Status | Evidence |
|---|---|---|
| Registration before outcomes were examined | met | OSF https://osf.io/kes3p/, registered 2026-11-01 05:49:21 UTC (`docs/preregistration.md:232`); the real run finished 2026-11-01T09:28:07Z (`p5_mpi_summary.csv` `run_created`) |
| Frozen plan identifiable | met | Tag `p5-freeze`, commit `22b8ace`, file SHA-256 at `docs/preregistration.md:226-230`; tag present on `origin` (checked 2026-11-04) |
| Code frozen with the plan | met | `docs/preregistration.md:213`; the run commit `13c078e` differs from `22b8ace` only in `CLAUDE.md`, `docs/STATUS.md`, `docs/osf-registration.md` and section 11 of the plan (`git diff --stat 22b8ace 13c078e`, checked 2026-11-04) |
| Prior knowledge disclosed | met | `docs/preregistration.md:39-52` |
| Deviations log | met, but see section 4 | `docs/preregistration-deviations.md:7` says none as of 2026-11-01 |
| Registration recorded in the verification log | missing | `PLAN.md` step 17 says the OSF URL and timestamp "go in a D-row"; `docs/verification.md` ends at D64 (`:86`) with no such row |
| Template named | met | Van den Akker et al. (2021), `VandenAkker2021` (`docs/preregistration.md:3`) |

### 2.3 Paper 2: STROBE plus survey-design items

| Item | Status | Evidence / what is missing |
|---|---|---|
| Design, setting, data source | met | `data/public/aggregates/README.md:71-76`; `docs/reproduce.md:7-16` |
| Case definition | met | DISABILITY3 per WG Document 7A (`data/public/aggregates/README.md:55`; `docs/verification.md:45`, D23) |
| Population and age groups | met | De facto members 5+, 18+ headline, 5–17 separate (`data/public/aggregates/README.md:40`, `:72`) |
| Weights, strata, PSU | met | `data/public/aggregates/README.md:72-76` |
| Variance estimation method | met | Taylor linearisation, R `survey` (`data/public/aggregates/README.md:45`); lonely PSUs `:76` |
| Interval method | met | Korn–Graubard (`data/public/aggregates/README.md:46`) |
| Design df, effective n, design effect | met | Columns `df`, `n_effective` (`data/public/aggregates/README.md:48-49`) |
| Response rates | **missing** | DHS household and individual response rates are not stated anywhere in the repo (searched `docs/`, `data/`, `site/methodology.html` on 2026-11-04) |
| Item non-response | met | "Don't know" handling (`data/public/aggregates/README.md:58`; `docs/verification.md:70`, D48) |
| Proxy reporting | partly | Stated generally (`data/public/aggregates/README.md:82`); no figure for the share of DHS answers given by proxy |
| Precision standard | met | NCHS (Parker et al., 2017) plus a 10-event rule (`data/public/aggregates/README.md:64-68`) |
| Disclosure control | met | `data/public/aggregates/README.md:63`; secondary suppression and its limits (`docs/verification.md:71`, D49) |
| Validation against published tables | met | 1,360 cells match FR395 (`docs/verification.md:70`, D48) |
| Second implementation | met | Python `svy` vs R `survey` (`docs/verification.md:70`) |
| Age standardisation for between-state comparison | **missing** | State estimates are crude; states differ in age structure (C1 share 60+ from 2.4% to 7.1%, `data/public/covariates/README.md:36`). Not discussed anywhere |
| Model-based alternative | met | Fay-Herriot tried and reported (`docs/fay-herriot-covariates.md:62-90`) |
| Comparison with other sources | met | NDHS tables (D46), JONAPWD (`data/public/jonapwd/README.md:5`), WHO 16% (D59) |
| Limitations next to results | met | `data/public/aggregates/README.md:78-83` (added in this pass) |
| Data availability | met | Public aggregates in repo; restricted access path in `docs/reproduce.md:7-16` |
| Ethics statement | **missing** | No statement on ethical approval or exemption for secondary analysis of de-identified data (both papers) |
| Funding, competing interests, AI-assistance statement | missing | The plan discloses AI drafting of code (`docs/preregistration.md:6`); no journal-style statement exists |

### 2.4 Paper 3: JOSS review checklist

Criteria from `JOSS2026Review` (review criteria) and `JOSS2026Submitting` (submission requirements), both read 2026-11-04. Line numbers refer to the files on branch `academic-polish` after the docs commit.

| # | Criterion | State | Evidence |
|---|---|---|---|
| 1 | OSI-approved licence file in the repository | **Met** | `packages/disability-access-charts/LICENSE:1` (MIT); `pyproject.toml:7-8` (`license = "MIT"`, `license-files`); root `LICENSE` |
| 2 | Scope and significance (research impact) | **Partly met** | Used by one project (Curb Cut: `site/public/data/charts/*.json`, `packages/transform/scripts/build_charts.py`). No external users, citations or integrations yet |
| 3 | Statement of need (problem, audience, relation to other work) | **Partly met** | Problem and relation to other work: `README.md:5`, `README.md:139-147` ("How it compares"). Target audience is not stated explicitly (who should use it: survey statisticians, data journalists, site builders?) |
| 4 | Installation with dependencies documented and automated | **Met** | `README.md:42-43` (`pip install`, optional `[plotly]` extra); `pyproject.toml:26-29` (no core dependencies); on PyPI as 0.3.0 |
| 5 | Example usage, ideally on a real problem | **Met** | `README.md:60-87` (claim checker example); `examples/` (four scripts: JONAPWD 2025 figures, synthetic dot plot, synthetic patterned map, plain Plotly audit), run by `tests/test_examples.py` |
| 6 | API / functionality documentation | **Partly met** | Narrative docs: `docs/claim-checker.md`, `docs/findings.md`, `docs/maps.md`, `docs/patterns.md`; detailed module docstrings (e.g. `src/disability_access_charts/describe.py:1-60`, `vision.py:1-42`, `audit.py:1-24`). No generated API reference (Sphinx / mkdocs) and no hosted documentation site |
| 7 | Functionality (reviewer installs and verifies) | **Met, as far as can be checked here** | `uv run pytest packages/disability-access-charts`: 436 passed (2026-11-04). Clean installs from PyPI checked by hand for 0.2.0 (3.12 and 3.10) and 0.3.0 (3.12 only) (`docs/STATUS.md:92`, `:330`) |
| 8 | Automated tests with CI | **Met** | 17 test files under `packages/disability-access-charts/tests/`; CI runs pytest with an 85% coverage floor (`.github/workflows/ci.yml:37`) and `disability-access-charts check --strict` on the site's chart JSON (`ci.yml:98`). CI runs Python 3.12 only, although `requires-python = ">=3.10"` (`pyproject.toml:6`) |
| 9 | Community guidelines (contributing, issues, support) | **Missing** | No `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue templates or support statement. Only an Issues URL in `pyproject.toml:36` |
| 10 | Development timeline (preferably 6+ months, steady) | **Missing** | First commit touching the library 2026-10-16 (`git log --reverse -- packages/disability-access-charts`), commits on 7 distinct dates |
| 11 | Open development (releases, issues, PRs) | **Partly met** | Tags `charts-v0.0.1`, `charts-v0.1.0`, `charts-v0.2.0`, `charts-v0.3.0`; PRs #2–#6 merged. Few or no public issues |
| 12 | Collaborative effort | **Partly met** | Two committer names in `git shortlog` (125 and 6 commits); whether the second is a separate person was not checked. No outside contributions identified. A single-author project must show community engagement in the paper |
| 13 | Good practices (licence, docs, tests, releases, contribution path) | **Partly met** | All present except a contribution path (item 9) |
| 14 | Paper: summary, statement of need, comparison, research use, references, archive link | **Missing** | No `paper.md` or `paper.bib`; no archived release (e.g. Zenodo DOI). A root `CITATION.cff` was added in this pass |
| 15 | State of the field, with a build-versus-contribute justification | **Partly met** | `README.md:139-147` compares a11yviz, maidr, Highcharts and AggChecker. No argument for why claim checking could not be contributed to an existing package (e.g. maidr) |
| 16 | Software design section | **Missing** (in a paper) | The design exists in the docs (one JSON document per chart, pure-Python core, audit in CI) but is not written up as trade-offs |
| 17 | Research impact statement | **Missing** | Only Curb Cut's own use |
| 18 | AI usage disclosure | **Missing** | Required by JOSS. Much of the code and documentation was written with Claude (commit trailers `Co-Authored-By: Claude`); the paper must say where and how output was verified |
| 19 | Authorship | **Met** | Single author; commit history shows the author's account |
| 20 | References / citation of prior work | **Partly met** | The library docs now cite WCAG 2.2, Machado et al. (2009), Luo et al. (2001), Sharma et al. (2005), Harrower and Brewer (2003), Benjamini and Hochberg (1995), Benjamini and Yekutieli (2001), Jo et al. (2019), Seo et al. (2024), Sharif et al. (2023), Parker et al. (2017). Missing: the wider literature on chart alt-text and accessible visualisation (e.g. chart-captioning and chart fact-checking work listed in `docs/verification.md` D18), not yet read or cited |

## 3. Substantive gaps a reviewer would raise

### 3.1 Papers 1 and 2

Each was checked against the documents and public files named.

1. **The exposure is not the WG-SS.** MPI asks seeing, hearing and walking severity only after a "yes" screener and only of aid users (`docs/verification.md:65`, D43). Acknowledged throughout (`docs/preregistration.md:63-82`; `docs/brief/p5-poverty-brief.md:34`). A reviewer will still ask how many exposed households come from the routing-free domains alone: S6 (self-care, remembering, communication) gives 12.4 points (6.3 to 18.9), close to the primary, which is the strongest answer and should be prominent in the paper.
2. **The "two bounds" logic did not hold.** The plan presents the primary and S5 as two bounds (`docs/preregistration.md:69`). S5 came out lower (5.4 points, 1.5 to 9.7) than the primary (11.7). The brief says so honestly (`docs/brief/p5-poverty-brief.md:34`), but the paper needs to explain why: S5 adds screener-only "yes" answers that do not separate some from a lot of difficulty, so it also dilutes the exposed group.
3. **Single cross-section: no temporal order.** Acknowledged (`docs/preregistration.md:123`, `:194`; brief `:23`). A reviewer will ask whether the head's education (`docs/preregistration.md:97`) and household composition (`:99`) are pre-exposure; both are handled by robustness runs (13.0 and 12.6 points, `p5_mpi_estimates.csv` `rob_no_head_education`, `rob_place_head_sex_age`).
4. **Positivity is weak, and the primary estimate leans on clipped propensities.** Only 680 of 51,422 households are exposed (1.3%); the exposed group's median propensity is 0.022 and its 25th percentile 0.010 (`p5_mpi_summary.csv` `quantile_exposed_*`). The propensity was clipped at 0.01 for 62.0% of people (63.7% of households; `overlap_clipped_share_*`). Clipping, as pre-registered (`docs/preregistration.md:135`), keeps those households but bounds their inverse weights, so the primary estimate is partly model extrapolation. The overlap-population estimate is 8.1 points (2.1 to 14.1) on 38.3% of people. The brief reports both (`:11-15`). Expect a request for an ATT (the average among exposed households, which needs far less overlap) or overlap weights as a post-hoc sensitivity analysis, labelled as a deviation.
5. **Learners and linear benchmark disagree by about a third.** DoubleML 11.7 vs survey-weighted LPM 8.0 (3.4 to 12.6) vs logistic-only learners 10.1 (`p5_mpi_estimates.csv`). The plan calls the LPM a "familiar check" (`docs/preregistration.md:150`); the paper should explain the gap (functional form, weighting of nuisance fits, clipping).
6. **Sensitivity to unmeasured confounding is modest.** RV 1.8% and RVa 1.0% (`p5_mpi_summary.csv` `rv`, `rva`); E-value 1.66, 1.42 for the CI limit; sensemakr with a confounder three times as strong as the head's education crosses zero (`sensemakr_3x`: 2.1, −0.8 to 4.9). The plan's own caveat that E-values are small by construction at a 60% base rate (`docs/preregistration.md:156`) should be in the paper, with the benchmarked bounds (place, sector, education all leave 10.7 to 12.7 points).
7. **Multiplicity.** Holm covers S1–S3 only (`docs/preregistration.md:172`); S4–S6, X1 (8 subgroups), 8 robustness runs and 6 leave-one-zone-out runs are unadjusted. This is pre-registered and labelled, but the urban/rural X1 contrast (29.4 vs 6.7 points) will draw attention; it must stay exploratory, with no interaction claim.
8. **Placebo calibration.** 8% of the 100 placebo intervals excluded 0, against about 5% expected (`p5_mpi_summary.csv` `placebo_share_ci_excluding_0`). Within binomial noise for 100 draws, but a reviewer may ask whether EA-clustered SEs without strata are slightly anti-conservative.
9. **Outcome measurement.** The rebuilt MPI matches national H within 0.1 points, but partly through offsetting indicator errors (nutrition −5.1, fuel +4.5, water reliability +4.1; `docs/verification.md:86`, D64). Whether those errors differ by exposure is unknown. The Table 7 reproduction (72.0 vs 71.4; 61.8 vs 61.8) is the best available evidence that the household-level classification is right; it should be presented as such.
10. **Survey design assumptions.** No strata variable is shipped with MPI 2021; strata are assumed (`docs/verification.md:62`, D40), and the DoubleML SEs ignore strata (`docs/preregistration.md:61`).
11. **Fay-Herriot not used (paper 2).** All 26 arcsine-normal models failed Shapiro–Wilk, driven by Taraba and Abia, and shrinkage was negligible (γ 0.93–0.96) (`docs/fay-herriot-covariates.md:71-85`; D56). The pre-declared rule did not cover "every model fails" (`:86`). A reviewer may ask for the log-scale FH that the author judged would pass (`:75`) as a sensitivity analysis. The argument that direct estimates suffice (CV 10–27%, all 37 reliable; `docs/fay-herriot-covariates.md:7`, checked against `dhs2024_state.csv` on 2026-11-04) is sound for DISABILITY3 18+ but not for single domains, where 9–35 of 37 states are reliable (`docs/verification.md:80`, D58).
12. **GHS power and design (E1).** 364 onset cases (`p5_ghs_summary.csv`); the consumption MDE was 0.494 SD, just under the 0.5 SD run rule, with an intra-cluster correlation of 0.22 and a design effect of 11.0. The work estimate (−26.4 points, −33.2 to −19.7) is large; a reviewer will raise reverse ordering within the five-year gap (stopping work, then reporting difficulty), the reworded W5 items (`docs/preregistration.md:203`, `:206`), and attrition: attriters were younger (standardised difference in age 0.32) and more often severe in W4 (3.2% vs 2.0%; `attrition_*`). It is labelled exploratory everywhere; keep it so.
13. **External validity of state estimates and the effect of suppression.** Suppression hits only state × wealth quintile cells, 413 in 16 states (`data/public/aggregates/README.md:63`); headline state estimates are unaffected. Crude (not age-standardised) state prevalence is the larger issue (section 2.3).
14. **JONAPWD figures are neither survey estimates nor registration counts.** They are the global 15% benchmark applied to population projections (`data/public/jonapwd/README.md:5`); r = 0.998 with population (D17). Any paper must not call them administrative data.
15. **DHS age.** 49 people with "don't know" age are outside every age group, so outside the 18+ headline (`docs/verification.md:70`, D48); negligible but should be footnoted.
16. **Reporting of two DHS definitions.** WG Doc 7A makes DISABILITY3 missing when a domain is "don't know" and none is severe, where DHS codes 0 (D48). State it in the paper's methods.

### 3.2 Paper 3

#### 3.2.1 No evaluation with screen-reader users

The library's purpose is accessibility, but no screen-reader user has used its output. The author is not a screen-reader user (`CLAUDE.md`, "What the project is"); the site's NVDA checks are first-time-user checks, partly scripted with Guidepup (`docs/STATUS.md:112`). The generated wording follows Sharif et al. (2023), a six-page interview study, but whether the library's descriptions, tables and findings sentences help screen-reader users is untested. Any accessibility venue will treat this as the main weakness; JOSS will accept the software without it but the paper must not imply it.

#### 3.2.2 Claim-checker accuracy is unmeasured

The checker's rules are fully documented (`docs/claim-checker.md`) and the test suite exercises each claim form, but there is no measurement of:

- **false negatives**: false claims it passes, because it does not recognise the wording (it warns on some unrecognised wording, not all; `claim-checker.md`, "Not understood at all");
- **false positives**: true claims it rejects (known cases are listed as "0.1.1 follow-ups" in `docs/STATUS.md:213`);
- performance on **real descriptions** (human-written alt-text, news captions, LLM output) as opposed to test strings written by the author.

A reviewer will ask for precision and recall on a labelled corpus, ideally one not written by the author.

#### 3.2.3 No comparison benchmark

The README comparison (`README.md:139-147`) is descriptive and dated. No tool was run side by side. A fair benchmark would cover the overlap that exists: alt-text generation (maidr's text descriptions, Highcharts' description handling), contrast auditing (a11yviz), and claim checking against AggChecker-style systems (Jo et al., 2019) on chart-sized data. Plotly's own accessibility support was not checked for this report and should be before any claim about it is made.

#### 3.2.4 Validity of the colour-vision screening

The check uses Machado et al. (2009) at severity 1.0 and CIEDE2000 thresholds of 5 (error) and 10 (warning). The thresholds are design choices, not derived from perception data (`vision.py:26-41`), and the docs now say so (`docs/maps.md:61-63`). A reviewer will ask: why these thresholds; why only full dichromacy; how simulated differences relate to discrimination of map classes at map scale, under a pattern, on real screens. Either cite evidence for the thresholds or run a small discrimination study.

#### 3.2.5 Generality beyond Curb Cut

Every real example is Nigerian disability prevalence; the defaults (percent units, 95% survey intervals, NCHS precision flags, Nigerian state maps) follow that use. The core claim checker is not specific to it, but nothing shows it working on other domains, other chart types (only bar, grouped bar, dot and choropleth; line charts and time series are not supported, and "trends over time" are not understood), or other languages (English only). A reviewer will ask for at least one worked example outside Curb Cut.

#### 3.2.6 API stability

`Development Status :: 3 - Alpha` (`pyproject.toml:21`). Each minor release has changed defaults: 0.2 changed the default map document (patterns on), 0.3 changed the default scheme and the map schema (`"1.1"`) and made custom themes subject to new error checks (`README.md:19-22`). There is no deprecation policy or stated versioning scheme. A reviewer will want a 1.0 or a written stability promise before publication.

#### 3.2.7 Statistical method

The findings block is documented carefully (`docs/findings.md`), including its approximations (independence, normal intervals, nominal FDR under unproven positive dependence). A statistician reviewer may still ask for a design-based test using the covariance between estimates, which the library cannot do because it receives only intervals. This is a stated limitation, not an error.

## 4. Problems noted in frozen files (not changed)

- `docs/preregistration.md:3`: the status line still says "not yet registered", while section 11 (`:232`) records the OSF registration. Only section 11 may change after the freeze, so the status line is stale by rule. A reader of the frozen file on OSF sees the pre-registration state, which is correct for that copy; the repo copy could carry a pointer in section 11.
- `docs/preregistration.md:59`: "fewer than 30 **weighted** households that refused" mixes a disclosure count (unweighted) with "weighted"; probably "fewer than 30 households, weighted or not".
- `docs/preregistration.md:69`: the primary and S5 are described as "two bounds"; the result shows S5 is not an upper bound (section 3.1, item 2). This is a reasoning error in the plan, not a deviation; it is handled in the brief.
- `docs/preregistration.md:135`: "Propensity scores are clipped" is correct, but the plan did not anticipate that clipping would bind for most households; no deviation is needed, but the paper should say it.
- `docs/preregistration-deviations.md:7`: "No deviations as of 2026-11-01". No undeclared deviation was found in the public files. Two items could be logged as notes rather than deviations: the run was made from `13c078e`, not the freeze commit (documentation-only differences), and the propensity learner chosen was logistic although the forest had the lowest mean loss (allowed by the one-standard-error rule, `docs/preregistration.md:144`).
- `docs/osf-registration.md:5`: "works once the tag is pushed": the tag is now on `origin` (checked 2026-11-04), so the note is obsolete but harmless.

## 5. Wording suggestions for the generated brief and results page (not changed)

Source: `docs/brief/p5-poverty-brief.md` (generated by `packages/transform/scripts/build_brief.py` from `poverty_text.py`).

- `p5-poverty-brief.md:9` (`poverty_text.py:198-203`, `comparison_rates`): "In comparable households without such a member, 62.9% of people are multidimensionally poor" uses μ₀ (0.6287), which happens to round to the national H (62.9%). Add "(a model-standardised figure)" so readers don't take it for the national rate.
- `p5-poverty-brief.md:11-15`: add that the propensity was clipped at 0.01 for about six in ten people, which is why the overlap estimate is shown.
- `p5-poverty-brief.md:16` (`poverty_text.py:206-222`, `missing_line`): give the analysed count too (51,422 households, 680 exposed), so the denominators of the headline are visible.
- `p5-poverty-brief.md:26-32`: name the quantity: "the robustness value is 1.8% (1.0% for the interval)". Readers of a brief will not know "what is left unexplained" without the term.
- `p5-poverty-brief.md:49`: "centred near zero" could add "and the real estimate was more extreme than all 100 (empirical p = 0.0099)", which is the pre-registered statistic (`docs/preregistration.md:164`).
- `p5-poverty-brief.md:53-54`: the linear model's 8.0 points sits under the headline without comment; one clause ("a simpler model that assumes a straight-line relationship") would prevent the reader from treating the gap as a contradiction.
- `p5-poverty-brief.md:58-59`: S2 and S3 are "supported" after Holm's correction; say so, since the brief otherwise gives intervals only.
- `p5-poverty-brief.md:69-70`: the GHS work result could add "a difficulty may also follow a change in work within the five years, so the order is unknown", mirroring the MPI reasons.
- `p5-poverty-brief.md:98`: "NBS and the World Bank" here vs "National Bureau of Statistics, Nigeria … World Bank Microdata Library" in `data/public/aggregates/README.md:89`; use one form.
- `p5-poverty-brief.md:100-102`: the DHS final report's current title is "Nigeria Demographic and Health Survey 2024" (FR395); its author list should be checked (see section 7).

## 6. Doc–code contradictions found

### 6.1 Analysis and data docs (not fixed)

- `CLAUDE.md` ("What the project is" → Analysis) and `PLAN.md:286`, `:288`: DoWhy refutations and an "event study … checked against R `did`". The code has no DoWhy dependency (`packages/ingest/pyproject.toml`) and writes its refutations around DoubleML (`docs/verification.md:84`, D62); the GHS check uses R `fixest` 0.14.2 (`DESCRIPTION`; `p5_ghs_summary.csv` `*_fixest`), and the design is a two-period comparison, which `poverty_text.py:32` forbids calling an event study.
- `CLAUDE.md` names `emdi` with `sae`; only `sae` is used (`DESCRIPTION`; D47).
- `docs/verification.md:84` (D62) lists R `EValue` 4.1.4; it is not in `renv.lock`, and the E-value is computed in Python (`packages/ingest/src/curbcut_ingest/restricted/p5_mpi.py:825-833`).
- `docs/verification.md:23` (D1, 52,022 interviewed) vs `:63` (D40, 53,415 interviewed); `docs/preregistration.md:34` uses 53,415 in the identification file and `:59` 52,022 completed. Likely file rows vs completed interviews; one sentence should reconcile them.
- `docs/reproduce.md:18-35`: the hash table covers MPI Sections A, B and D only, but `mpi2021_poverty` and `p5_exposure` read further sections (C, E, F, H, I, J, K, Q, R, T per D64 and `docs/reproduce.md:73`), and `p5_ghs` reads GHS consumption and labour files; their hashes are in each run's manifest but not in the doc. Adding them needs restricted access.
- `docs/verification.md:45` (D23) says WG Doc 7A judges disability "without the use of assistive technology"; the WG-SS seeing and hearing questions say "even if wearing glasses / using a hearing aid". Re-read the source before citing D23's wording.
- Fixed in this pass (doc-only, no code touched): `data/README.md` said the MPI aggregates were git-ignored until NBS replied (they have been public since 2026-10-24, D4); `data/public/aggregates/README.md` said the files were "not shown on the site yet" and listed 168 suppressed cells in `dhs2024_state.csv` (the file has 413: 168 primary, 245 complementary); `README.md` "Status" still described P2; `docs/reproduce.md` said `renv::restore()` installs three packages (it installs the seven in `DESCRIPTION`).

### 6.2 Library docs

Recorded, not fixed in code. Where this pass changed only a doc's wording to stop over-claiming, that is said.

1. **"About twice a just-noticeable difference."** `docs/maps.md:61` says the error threshold `CVD_MIN_DELTA_E = 5` is "about twice a just-noticeable difference". The code's own docstring (`src/disability_access_charts/vision.py:29-31`) says a CIEDE2000 difference of about 1 is roughly the just-noticeable difference, which would make 5 about five times it. **Left as is in both places**; needs the author's decision and a citation for the JND value.
2. **Claim checker on "any Plotly figure".** The README said the checker "runs on any Plotly figure in CI". `audit()` runs it on a plain figure only when `alt_text=` is passed and only for bar and scatter traces with string categories and numeric values (`src/disability_access_charts/audit.py:626-657`, `:720`); otherwise it warns `alt-text-not-checked` (`audit.py:236-245`). **README wording narrowed** (`README.md:5`) to match the code; code unchanged.
3. **Python 3.10.** The README said "3.10 is checked by installing the wheel and running the examples", implying a standing check. CI runs 3.12 only (`.github/workflows/ci.yml`; `tests/test_smoke.py:8` says so), and the 3.10 install was checked by hand for 0.2.0 but not for 0.3.0 (`docs/STATUS.md:92`, `:151`, `:330`). **README wording corrected** to say so (`README.md:136`).
4. **Version of the claim-checker reference.** `docs/claim-checker.md` said it was the reference "in 0.2". `describe.py` has not changed since before the 0.2.0 tag (`git log -- src/disability_access_charts/describe.py`: last commit `6d778e8`, the commit tagged `charts-v0.2.0`). **Changed to "0.3; the rules have not changed since 0.2".**
5. **"Colour-blind-safe."** The README called the default scheme "colour-blind-safe". The code checks only simulated full dichromacy against design thresholds (section 6.2, item 1; section 3.2.4). **README wording narrowed** to "chosen to stay distinguishable under simulated colour-vision deficiency". The same phrase remains in `CHANGELOG.md` (not in this executor's files).
6. **Description vs PyPI.** The README's a11yviz description was checked against 0.1.8 (2026-10-29); PyPI shows 0.1.9 on 2026-11-04. Not a contradiction (the check is dated), but it needs rechecking before a paper.

No numerical value in the library docs disagreed with the code: every contrast ratio, CIEDE2000 minimum, CIELAB L\* value and ink ratio in `docs/maps.md` and `docs/patterns.md`, and the 73 / 20 / 15 counts in `docs/findings.md` (against `site/public/data/charts/prevalence_by_state.json`), were recomputed from the 0.3.0 code on 2026-11-04 and match.

## 7. Unverified citations (`TODO(verify)` in `docs/references.bib`)

| Key | What is unverified |
|---|---|
| `NDHS2024` | Author list and exact title: from the DHS Program listing via a search result; the page returned 403 to scripted fetches |
| `GHSW4`, `GHSW5` | Exact citation wording, year and the download date the World Bank terms ask for |
| `NBS2023Demographic` | Publication year as printed |
| `WHO2006Growth` | ISBN |
| `KornGraubard1998` | Page range 193–201 (sources disagree on volume 23 vs 24; the Statistics Canada record puts it in issue 1998002, volume 24) |
| `Parker2017NCHS` | Full author list (D42 records the first three, "et al."); the CDC URL returned 403 to a scripted check on 2026-11-04 (the document itself was checked from the primary PDF on 2026-10-24, D42) |
| `Svy` | Authors and preferred citation |
| `RFixest` | Preferred citation |
| `RSensemakr` | Author list |
| `A11yviz2026PyPI` | Author not recorded |
| Venue quartiles | Every journal in section 1.1, and IEEE TVCG, ACM TACCESS and Computer Graphics Forum in section 1.2: not confirmed on SCImago or JCR |

Every DOI in the bib resolved on 2026-11-04 (Crossref titles matched for all Crossref DOIs; DataCite and EU DOIs redirect). One title mismatch is recorded, not changed: WorldPop v3.0's DOI is registered as "Modelled gridded population estimates for Nigeria 2025 (version 3.0)", while the release README's attribution (quoted in `data/public/worldpop/README.md:9`) says "Bottom-up gridded population estimates for Nigeria, version 3.0".

`Sharma2005CIEDE2000` is dated 2004 online by Crossref and 2005 by the journal issue (30(1)); the bib uses 2005.

## 8. Glossary

One list for all three papers. Use these terms, with these meanings, in any manuscript. Rows marked "(library)" come from the chart library's docs.

| Term | Definition | Where defined |
|---|---|---|
| WG-SS | Washington Group Short Set on Functioning: six questions (seeing, hearing, walking, remembering or concentrating, self-care, communication), four answers (no difficulty, some, a lot, cannot do at all) | `data/public/aggregates/README.md:55-58` |
| DISABILITY3 | At least one WG-SS domain at "a lot of difficulty" or "cannot do at all" (WG Document 7A) | `data/public/aggregates/README.md:55`; D23 |
| Severe difficulty (P5) | "A lot" or "cannot do" on MPI's own items; not DISABILITY3 | `docs/preregistration.md:65-71` |
| Any difficulty / NBS broad definition (S2) | "Some difficulty" or worse in any MPI item, or a skin condition | `docs/preregistration.md:75-82`; D61 |
| Household exposure | The household has at least one member aged 5+ with a severe difficulty | `docs/preregistration.md:10`, `:73` |
| H, A, M0 (MPI) | Incidence (share of people poor), intensity (average deprivation share among the poor), and M0 = H × A (Alkire and Foster, 2011); poor at k = 26% | D61, D64; `docs/preregistration.md:86` |
| Adjusted association | The standardised risk difference, interpreted without a causal claim | `docs/preregistration.md:16`, `:127`, `:193` |
| Design-based SE | Standard error that reflects weights, strata and clustering (Taylor linearisation) | `data/public/aggregates/README.md:5`, `:45` |
| CV | Coefficient of variation, SE / estimate | `data/public/aggregates/README.md:5` |
| Effective n | p(1−p)/SE², capped at n (NCHS) | `data/public/aggregates/README.md:48` |
| Design df | PSUs with a respondent in the cell minus their strata | `data/public/aggregates/README.md:49` |
| Suppression threshold | A cell whose denominator has fewer than 30 unweighted respondents is suppressed; complementary suppression prevents recovery by subtraction | `data/public/aggregates/README.md:63`; `disclosure.py:54` |
| Precision flag | reliable / review / unreliable per NCHS standards plus a 10-event rule | `data/public/aggregates/README.md:64-68` |
| Overlap population | Households with a cross-fitted propensity between 0.01 and 0.99 | `docs/preregistration.md:145` |
| Robustness value (RV) | Share of residual variance an unmeasured confounder must explain in both exposure and outcome to bring the estimate to zero (Chernozhukov et al., 2022; Cinelli and Hazlett, 2020) | `docs/preregistration.md:154`; brief `:26-30` (not named) |
| E-value | Minimum risk-ratio association a confounder needs with both exposure and outcome to explain the estimate away (VanderWeele and Ding, 2017) | `docs/preregistration.md:156` |
| Direct estimate | A state estimate from that state's sample only | `data/public/aggregates/README.md:80` |
| Fay-Herriot model | Area-level model combining direct estimates with covariates (Fay and Herriot, 1979) | `docs/fay-herriot-covariates.md:27-35` |
| GVF | Generalised variance function: smoothed sampling variances | `docs/fay-herriot-covariates.md:30`, `:45` |
| MDE | Minimum detectable effect at 80% power, α = 0.05 | `docs/preregistration.md:208` |
| Alt-text (library) | The text alternative for a chart (WCAG 2.2 SC 1.1.1); here built from the data, summary first | `README.md:5`; `docs/claim-checker.md:5` |
| Description (library) | Any text about a chart: alt-text, caption or LLM rewording | `docs/claim-checker.md:5` |
| Claim (library) | A statement in a description that the checker recognises and tests against the data | `docs/claim-checker.md:5` |
| Claim checker (library) | `check_alt_text`: tests numbers and recognised claims in a description against the chart's data | `README.md:5`; `docs/claim-checker.md` |
| Category / series (library) | A labelled position on the chart / one set of values across the categories | `docs/claim-checker.md:5` |
| Error / warning (library) | A claim found false / wording not tested or a result to read with care; only errors fail an audit | `docs/claim-checker.md:5`; `audit.py:17-19` |
| Supported (difference) (library) | Passes the interval test (claim checker) or survives the BH correction (findings) | `docs/claim-checker.md` ("With confidence intervals"); `docs/findings.md:5` |
| Estimate / comparison (library) | One plotted value with its interval / one test of a difference between two estimates or an estimate and a reference | `docs/findings.md:5` |
| False discovery rate (FDR) (library) | Expected share of false positives among the comparisons reported as supported | `docs/findings.md:5`; `README.md` ("New in 0.2") |
| Family (of comparisons) (library) | One of four comparison types fixed in advance: `extremes`, `gaps`, `rankings`, `outliers` | `docs/findings.md:9-20` |
| Precision flag (library) | `reliable`, `review`, `unreliable` or `suppressed`, per estimate | `docs/findings.md:37-45` |
| Contrast ratio (library) | (L1 + 0.05) / (L2 + 0.05) of relative luminances (WCAG 2.2) | `docs/maps.md:5`; `contrast.py:38-43` |
| CIEDE2000 (library) | Perceptual colour difference in CIELAB (Luo et al., 2001) | `docs/maps.md:5` |
| Simulated colour-vision deficiency (library) | Machado et al. (2009) matrices at severity 1.0 for protanopia, deuteranopia, tritanopia | `docs/maps.md:61-63`; `vision.py:8-16` |
| Class / neighbouring classes (library) | One value range with one fill / classes adjacent in the class order (not adjacent regions) | `docs/maps.md:5` |
| Fixed classes (library) | Classes from rounded breaks given in advance, not quantiles | `docs/maps.md` ("Fixed classes") |
| Edge / halo / cased boundary (library) | Narrow boundary stroke / wider stroke drawn under it / the pair | `docs/maps.md:5`, "Cased boundaries" |
| Tile / ink / fill / ink weight (library) | Pattern unit (12 × 12) / colour of the pattern's shapes / colour under them / share of the tile the ink covers | `docs/patterns.md:5` |
| Legend filter (library) | Legend buttons that show one class at a time, with announced sentences | `docs/maps.md` ("The legend filter") |
| Chart document (library) | The JSON dict each builder returns (`plotly`, `alt_text`, `table`, `data`, `themes`, `audit`, …) | `README.md` ("What you get") |

Terms used but not defined at first use anywhere: "PSU" (used in `data/public/aggregates/README.md:72-76` without expansion), "EA" (enumeration area, expanded only in `docs/preregistration.md:61`).

## 9. What to do next

Ordered. S = under a day, M = a few days, L = a week or more. Items 1–6 help every paper; the rest are per paper.

1. **S** — Add a D-row for the OSF registration (URL, timestamp, attached-file hash), as `PLAN.md` step 17 requires.
2. **S** — Resolve the `TODO(verify)` citations in section 7 by hand, and confirm each venue's quartile on scimagojr.com along with its author guidelines (word limits, data policy).
3. **S** — Reconcile the doc–code contradictions in section 6: `CLAUDE.md` and `PLAN.md` on DoWhy, `did`, `emdi` and "event study"; D62 on `EValue`; the D1 vs D40 counts; the just-noticeable-difference sentence in the library's `docs/maps.md`; "colour-blind-safe" in `CHANGELOG.md`.
4. **S** — Write the ethics, funding, competing-interests, data-availability and AI-assistance statements once, for all papers.
5. **S** — Library: `CONTRIBUTING.md`, a code of conduct, issue templates, and a Zenodo archive of each release (JOSS items 9 and 14).
6. **S** — Library: add a Python 3.10 CI job, or raise `requires-python` to 3.12 (section 6.2, item 3).
7. **M** — Paper 1: publish a descriptive table by exposure (weighted, through the disclosure gate) and the unadjusted poverty gap under the primary definition (STROBE 14a, 15, 16a).
8. **M** — Paper 1: a post-hoc positivity sensitivity analysis (ATT or overlap weights), logged in `docs/preregistration-deviations.md` as an addition, not a replacement.
9. **M** — Paper 2: age-standardised state prevalence as a secondary table, and DHS response rates from FR395 Chapter 1.
10. **M** — Paper 3: a stability and deprecation policy, a generated API reference, a worked example outside Curb Cut, and the state-of-the-field reading (sections 3.2.5, 3.2.6; JOSS items 6, 15, 20).
11. **L** — Paper 3: a claim-checker accuracy study on a labelled corpus not written by the author, and an evaluation with regular screen-reader users (sections 3.2.1, 3.2.2). The second is needed for ASSETS, TACCESS or VIS, not for JOSS.
12. **L each** — Draft the manuscripts: introduction with a literature review (none is in the repo), methods from `docs/preregistration.md` and `docs/reproduce.md`, results from the public CSVs, a flow diagram. JOSS (paper 3) is not possible before about 2027-04 (six months of public development history).

**Decision for the author:** paper 1 is the closest to submission. It needs items 1–4, 7 and 8 first, then item 12 for paper 1 alone.
