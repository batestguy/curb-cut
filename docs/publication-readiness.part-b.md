# Publication readiness, part B: the software paper (`disability-access-charts`)

Status: draft for review, 2026-11-04. Scope: paper 3, a software paper on `disability-access-charts` 0.3.0 (`packages/disability-access-charts/`). Part A (the other papers and the shared bibliography) is a separate file. Citation keys refer to the part-B BibTeX entries, to be merged into `docs/references.bib`.

Everything below was checked against the repository at commit `e1dbb4c` plus the docs commit `5fa9878` on branch `academic-polish`, and against the venues' own pages on 2026-11-04. Where a fact could not be confirmed it says so.

## 1. Candidate venues

| Venue | Type | Fit | Indexing / ranking | Main obstacle now |
|---|---|---|---|---|
| **Journal of Open Source Software (JOSS)** | Journal, open review on GitHub, short `paper.md` plus the software | Best fit: reviews the software itself, not a study | Papers get a Crossref DOI (`joss2026submitting`). JOSS's own pages say nothing about Scopus, Web of Science or quartiles; it is **not a Q1 journal in the usual (JCR / SJR) sense** and should not be presented as one | Development history (section 2, item 10): commits on the library start 2026-10-16, about three weeks ago; JOSS asks for an extended public history, preferably 6 months or more, and treats work concentrated just before submission as unacceptable |
| **ACM ASSETS** (International ACM SIGACCESS Conference on Computers and Accessibility) | Peer-reviewed conference (full papers, short papers / posters, demos) | Good fit for an accessibility contribution, but expects an evaluation with disabled users; a demo or poster is the realistic first step | A conference: journal quartiles do not apply | Needs a study with screen-reader users (section 3.1) |
| **IEEE VIS short papers** (published in IEEE TVCG's proceedings track or IEEE Xplore) / **IEEE TVCG** | Conference / journal | Fits the visualisation side (claim checking of chart text, colour-vision screening, FDR-controlled findings) | TVCG is widely reported as Q1; **not confirmed here** (SCImago returned 403 to an automated check) — TODO(verify) | Needs a novel contribution beyond engineering, plus an evaluation (accuracy of the claim checker on a corpus, and a user study) |
| ACM TACCESS (Transactions on Accessible Computing) | Journal | Fits a fuller paper with a user evaluation | A secondary aggregator lists it as Q2 (JCR and SJR); **not confirmed** — TODO(verify) | Same evaluation gap as ASSETS |
| Computer Graphics Forum (EuroVis short papers) | Journal / conference | Possible for the colour and map work | Quartile **not confirmed** — TODO(verify) | Novelty of the map rules is modest on its own |

Recommendation: JOSS first, once the development-history condition can be met (about 2027-04 at the earliest, six months after the first commit), with an ASSETS poster or demo, or a VIS short paper, when a screen-reader user study and a claim-checker accuracy study exist. Do not describe JOSS as Q1.

## 2. JOSS review checklist against the current repository

Criteria from `joss2026review` (review criteria) and `joss2026submitting` (submission requirements), both read 2026-11-04. Line numbers refer to the files on branch `academic-polish` after the docs commit.

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
| 14 | Paper: summary, statement of need, comparison, research use, references, archive link | **Missing** | No `paper.md` or `paper.bib`; no archived release (e.g. Zenodo DOI); no `CITATION.cff` |
| 15 | State of the field, with a build-versus-contribute justification | **Partly met** | `README.md:139-147` compares a11yviz, maidr, Highcharts and AggChecker. No argument for why claim checking could not be contributed to an existing package (e.g. maidr) |
| 16 | Software design section | **Missing** (in a paper) | The design exists in the docs (one JSON document per chart, pure-Python core, audit in CI) but is not written up as trade-offs |
| 17 | Research impact statement | **Missing** | Only Curb Cut's own use |
| 18 | AI usage disclosure | **Missing** | Required by JOSS. Much of the code and documentation was written with Claude (commit trailers `Co-Authored-By: Claude`); the paper must say where and how output was verified |
| 19 | Authorship | **Met** | Single author; commit history shows the author's account |
| 20 | References / citation of prior work | **Partly met** | The library docs now cite WCAG 2.2, Machado et al. (2009), Luo et al. (2001), Sharma et al. (2005), Harrower and Brewer (2003), Benjamini and Hochberg (1995), Benjamini and Yekutieli (2001), Jo et al. (2019), Seo et al. (2024), Sharif et al. (2023), Parker et al. (2017). Missing: the wider literature on chart alt-text and accessible visualisation (e.g. chart-captioning and chart fact-checking work listed in `docs/verification.md` D18), not yet read or cited |

## 3. Substantive gaps a reviewer would raise

### 3.1 No evaluation with screen-reader users

The library's purpose is accessibility, but no screen-reader user has used its output. The author is not a screen-reader user (`CLAUDE.md`, "What the project is"); the site's NVDA checks are first-time-user checks, partly scripted with Guidepup (`docs/STATUS.md:112`). The generated wording follows Sharif et al. (2023), a six-page interview study, but whether the library's descriptions, tables and findings sentences help screen-reader users is untested. Any accessibility venue will treat this as the main weakness; JOSS will accept the software without it but the paper must not imply it.

### 3.2 Claim-checker accuracy is unmeasured

The checker's rules are fully documented (`docs/claim-checker.md`) and the test suite exercises each claim form, but there is no measurement of:

- **false negatives**: false claims it passes, because it does not recognise the wording (it warns on some unrecognised wording, not all; `claim-checker.md`, "Not understood at all");
- **false positives**: true claims it rejects (known cases are listed as "0.1.1 follow-ups" in `docs/STATUS.md:213`);
- performance on **real descriptions** (human-written alt-text, news captions, LLM output) as opposed to test strings written by the author.

A reviewer will ask for precision and recall on a labelled corpus, ideally one not written by the author.

### 3.3 No comparison benchmark

The README comparison (`README.md:139-147`) is descriptive and dated. No tool was run side by side. A fair benchmark would cover the overlap that exists: alt-text generation (maidr's text descriptions, Highcharts' description handling), contrast auditing (a11yviz), and claim checking against AggChecker-style systems (Jo et al., 2019) on chart-sized data. Plotly's own accessibility support was not checked for this report and should be before any claim about it is made.

### 3.4 Validity of the colour-vision screening

The check uses Machado et al. (2009) at severity 1.0 and CIEDE2000 thresholds of 5 (error) and 10 (warning). The thresholds are design choices, not derived from perception data (`vision.py:26-41`), and the docs now say so (`docs/maps.md:61-63`). A reviewer will ask: why these thresholds; why only full dichromacy; how simulated differences relate to discrimination of map classes at map scale, under a pattern, on real screens. Either cite evidence for the thresholds or run a small discrimination study.

### 3.5 Generality beyond Curb Cut

Every real example is Nigerian disability prevalence; the defaults (percent units, 95% survey intervals, NCHS precision flags, Nigerian state maps) follow that use. The core claim checker is not specific to it, but nothing shows it working on other domains, other chart types (only bar, grouped bar, dot and choropleth; line charts and time series are not supported, and "trends over time" are not understood), or other languages (English only). A reviewer will ask for at least one worked example outside Curb Cut.

### 3.6 API stability

`Development Status :: 3 - Alpha` (`pyproject.toml:21`). Each minor release has changed defaults: 0.2 changed the default map document (patterns on), 0.3 changed the default scheme and the map schema (`"1.1"`) and made custom themes subject to new error checks (`README.md:19-22`). There is no deprecation policy or stated versioning scheme. A reviewer will want a 1.0 or a written stability promise before publication.

### 3.7 Statistical method

The findings block is documented carefully (`docs/findings.md`), including its approximations (independence, normal intervals, nominal FDR under unproven positive dependence). A statistician reviewer may still ask for a design-based test using the covariance between estimates, which the library cannot do because it receives only intervals. This is a stated limitation, not an error.

## 4. Doc–code contradictions found

Recorded, not fixed in code. Where this pass changed only a doc's wording to stop over-claiming, that is said.

1. **"About twice a just-noticeable difference."** `docs/maps.md:61` says the error threshold `CVD_MIN_DELTA_E = 5` is "about twice a just-noticeable difference". The code's own docstring (`src/disability_access_charts/vision.py:29-31`) says a CIEDE2000 difference of about 1 is roughly the just-noticeable difference, which would make 5 about five times it. **Left as is in both places**; needs the author's decision and a citation for the JND value.
2. **Claim checker on "any Plotly figure".** The README said the checker "runs on any Plotly figure in CI". `audit()` runs it on a plain figure only when `alt_text=` is passed and only for bar and scatter traces with string categories and numeric values (`src/disability_access_charts/audit.py:626-657`, `:720`); otherwise it warns `alt-text-not-checked` (`audit.py:236-245`). **README wording narrowed** (`README.md:5`) to match the code; code unchanged.
3. **Python 3.10.** The README said "3.10 is checked by installing the wheel and running the examples", implying a standing check. CI runs 3.12 only (`.github/workflows/ci.yml`; `tests/test_smoke.py:8` says so), and the 3.10 install was checked by hand for 0.2.0 but not for 0.3.0 (`docs/STATUS.md:92`, `:151`, `:330`). **README wording corrected** to say so (`README.md:136`).
4. **Version of the claim-checker reference.** `docs/claim-checker.md` said it was the reference "in 0.2". `describe.py` has not changed since before the 0.2.0 tag (`git log -- src/disability_access_charts/describe.py`: last commit `6d778e8`, the commit tagged `charts-v0.2.0`). **Changed to "0.3; the rules have not changed since 0.2".**
5. **"Colour-blind-safe."** The README called the default scheme "colour-blind-safe". The code checks only simulated full dichromacy against design thresholds (contradiction 1, section 3.4). **README wording narrowed** to "chosen to stay distinguishable under simulated colour-vision deficiency". The same phrase remains in `CHANGELOG.md` (not in this executor's files).
6. **Description vs PyPI.** The README's a11yviz description was checked against 0.1.8 (2026-10-29); PyPI shows 0.1.9 on 2026-11-04. Not a contradiction (the check is dated), but it needs rechecking before a paper.

No numerical value in the library docs disagreed with the code: every contrast ratio, CIEDE2000 minimum, CIELAB L\* value and ink ratio in `docs/maps.md` and `docs/patterns.md`, and the 73 / 20 / 15 counts in `docs/findings.md` (against `site/public/data/charts/prevalence_by_state.json`), were recomputed from the 0.3.0 code on 2026-11-04 and match.

## 5. Unverified citations

- `parker2017nchs` (NCHS data presentation standards): the CDC URL returned HTTP 403 to an automated fetch on 2026-11-04; the document itself was checked from the primary PDF on 2026-10-24 (`docs/verification.md` D42). TODO(verify) the URL in a browser.
- `a11yviz2026pypi`: author not recorded. TODO(verify).
- Venue quartiles for IEEE TVCG, ACM TACCESS and Computer Graphics Forum (section 1): not confirmed from SCImago or JCR. TODO(verify).
- All other entries: DOIs resolved through Crossref on 2026-11-04 (titles, authors, volumes and pages taken from Crossref), and URLs returned HTTP 200 on 2026-11-04. `sharma2005ciede2000` is listed by Crossref with a 2004 online date; the journal issue (30(1)) is 2005.

## 6. Glossary of terms used in the library docs

| Term | Definition | Where defined |
|---|---|---|
| Alt-text | The text alternative for a chart (WCAG 2.2 SC 1.1.1); here built from the data, summary first | `README.md:5`; `docs/claim-checker.md:5` |
| Description | Any text about a chart: alt-text, caption or LLM rewording | `docs/claim-checker.md:5` |
| Claim | A statement in a description that the checker recognises and tests against the data | `docs/claim-checker.md:5` |
| Claim checker | `check_alt_text`: tests numbers and recognised claims in a description against the chart's data | `README.md:5`; `docs/claim-checker.md` |
| Category / series | A labelled position on the chart / one set of values across the categories | `docs/claim-checker.md:5` |
| Error / warning | A claim found false / wording not tested or a result to read with care; only errors fail an audit | `docs/claim-checker.md:5`; `audit.py:17-19` |
| Supported (difference) | Passes the interval test (claim checker) or survives the BH correction (findings) | `docs/claim-checker.md` ("With confidence intervals"); `docs/findings.md:5` |
| Estimate / comparison | One plotted value with its interval / one test of a difference between two estimates or an estimate and a reference | `docs/findings.md:5` |
| False discovery rate (FDR) | Expected share of false positives among the comparisons reported as supported | `docs/findings.md:5`; `README.md` ("New in 0.2") |
| Family (of comparisons) | One of four comparison types fixed in advance: `extremes`, `gaps`, `rankings`, `outliers` | `docs/findings.md:9-20` |
| Precision flag | `reliable`, `review`, `unreliable` or `suppressed`, per estimate | `docs/findings.md:37-45` |
| Contrast ratio | (L1 + 0.05) / (L2 + 0.05) of relative luminances (WCAG 2.2) | `docs/maps.md:5`; `contrast.py:38-43` |
| CIEDE2000 | Perceptual colour difference in CIELAB (Luo et al., 2001) | `docs/maps.md:5` |
| Simulated colour-vision deficiency | Machado et al. (2009) matrices at severity 1.0 for protanopia, deuteranopia, tritanopia | `docs/maps.md:61-63`; `vision.py:8-16` |
| Class / neighbouring classes | One value range with one fill / classes adjacent in the class order (not adjacent regions) | `docs/maps.md:5` |
| Fixed classes | Classes from rounded breaks given in advance, not quantiles | `docs/maps.md` ("Fixed classes") |
| Edge / halo / cased boundary | Narrow boundary stroke / wider stroke drawn under it / the pair | `docs/maps.md:5`, "Cased boundaries" |
| Tile / ink / fill / ink weight | Pattern unit (12 × 12) / colour of the pattern's shapes / colour under them / share of the tile the ink covers | `docs/patterns.md:5` |
| Legend filter | Legend buttons that show one class at a time, with announced sentences | `docs/maps.md` ("The legend filter") |
| Chart document | The JSON dict each builder returns (`plotly`, `alt_text`, `table`, `data`, `themes`, `audit`, …) | `README.md` ("What you get") |

## 7. What to do next for paper 3

Ordered; S = under a day, M = a few days, L = a week or more.

1. **S** — Add `CONTRIBUTING.md` (with how to report an issue and get support), a code of conduct and issue templates (JOSS item 9).
2. **S** — Add `CITATION.cff` and archive each release on Zenodo (JOSS item 14).
3. **S** — Resolve the JND contradiction (section 4, item 1) with a cited value, and decide the "colour-blind-safe" wording left in `CHANGELOG.md`.
4. **S** — Add a Python 3.10 job to CI, or raise `requires-python` to 3.12 (section 4, item 3).
5. **M** — Write a stability and deprecation policy; plan 1.0 (section 3.6).
6. **M** — Generated API reference (mkdocs or Sphinx) hosted with the site (JOSS item 6).
7. **M** — A worked example outside Curb Cut, in another domain (section 3.5).
8. **M** — Read and cite the accessible-visualisation and chart fact-checking literature; write the state-of-the-field and build-versus-contribute argument (JOSS items 15, 20).
9. **L** — Claim-checker accuracy study: a labelled corpus of descriptions not written by the author (human alt-text, LLM output), precision and recall, published with the code (section 3.2).
10. **L** — Evaluation with regular screen-reader users of the generated descriptions, tables and findings sentences (section 3.1). Needed for ASSETS / TACCESS / VIS, not for JOSS.
11. **M** — Draft `paper.md` and `paper.bib` (summary, statement of need, state of the field, software design, research impact, AI usage disclosure) once items 1–8 are done.
12. **—** — Submit to JOSS when the development history reaches about six months of steady public work (no earlier than about 2027-04), with the accuracy study if it is ready.
