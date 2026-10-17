# P0 verification log

Every check that the design depends on, with its source and the date it was checked. A check is done only when **Result**, **Source** and **Checked** are filled in. Planning-stage findings (2026-10-16) are in `PLAN.md`; this file records the P0 confirmations.

Status key: ☐ open · ◐ partly confirmed (see notes) · ☑ confirmed · ✗ contradicts the plan (stop and revisit `PLAN.md`)

## Accounts

| # | Item | Status | Notes | Checked |
|---|---|---|---|---|
| A1 | PyPI account created, 2FA on | ☑ | 2FA is mandatory on PyPI | 2026-10-16 |
| A2 | `disability-access-charts` claimed on PyPI by publishing 0.0.1 from CI via trusted publishing (`a11y-viz` was blocked as too similar to the existing `a11yviz`) | ☑ | 0.0.1 published by run 38858669507; fresh `pip install` verified. https://pypi.org/p/disability-access-charts | 2026-10-16 |
| A3 | NBS microdata portal registration | ☑ | Account registered. MPI 2021 public-use request submitted and granted at once; the dataset is a 23.82 MB ZIP. | 2026-10-16 |
| A4 | World Bank Microdata Library registration | ☑ | Account registered by the author | 2026-10-16 |
| A5 | DHS Program registration (optional) | ☐ | Registration form is live again (no pause notice, 2026-10-16). Nigeria DHS 2024 (NG2024DHS) was released 2025-10-20 with 54 dataset files. Access needs a DHS account plus a project request (reviewed within about 24 h). | |

## Data and licensing

| # | Question | Status | Result | Source | Checked |
|---|---|---|---|---|---|
| D1 | Is NBS MPI 2021 representative at state level? (sampling documentation) | ◐ | Designed for it: 102 EAs per state (34 per senatorial district) × 15 households ≈ 1,530 households per state; 52,022 households interviewed (91.9% response). The catalog does not state precision; confirm with the report's sampling-error tables. No LGA-level estimates claimed in the catalog. | https://microdata.nigerianstat.gov.ng/index.php/catalog/71 | 2026-10-16 |
| D2 | Do GHS-Panel W3/W4 disability questions match W5's (Washington Group)? | ✗ | **Better than planned.** W4 (2018/19, file F48) has all six WG-SS questions: s4aq23 seeing, s4aq25 hearing, s4aq27 walking, s4aq29 remembering, s4aq31 self-care, s4aq33 communicating. W5 (2023/24, F9) has the same six: s3q23–s3q28. W5 adds "using your usual language" to the communication item, so check that the wording and response categories match. W3 (2015/16, F43) has only seeing (s4aq23) and walking (s4aq22b uphill, s4aq22d over 100 m). W4 and W5 are both public use. Catalog IDs: W3 2734 (`NGA_2015_GHSP-W3_v02_M`), W4 3557 (`NGA_2018_GHSP-W4_v03_M`), W5 6410 (`NGA_2023_GHSP-W5_v02_M`). | World Bank NADA API `/api/catalog/{idno}/variables` | 2026-10-16 |
| D3 | NBS republication terms: may weighted aggregates be published? | ◐ | Access by request with a confidentiality declaration (Statistical Act 2007 s.26, s.28); © NBS 2023; NBS says a full data access policy is still being developed. The access terms (agreed 2026-10-16) say the data are "used solely for reporting of aggregated information". They forbid redistribution without written agreement, re-identification, and linking datasets in ways that could identify individuals. **They require an electronic copy of every publication to be sent to the National Data Archive.** Required citation: "National Bureau of Statistics, Multidimentional Poverty index Survey 2021 v1.0". Access authority: Feedback@nigerianstat.gov.ng. | https://microdata.nigerianstat.gov.ng/index.php/catalog/71 | 2026-10-16 |
| D4 | NBS written confirmation that aggregates may be published (email sent / reply) | ☐ | | | |
| D5 | World Bank Microdata Library terms for GHS-Panel aggregates | ◐ | W3 is "Public use files, accessible to all" after a confidentiality declaration; users may not copy files or try to identify respondents; citation with reference number and download date required. W4/W5 have the same conditions. No explicit rule on derived aggregates; the separate Terms of use page is not yet read. | https://microdata.worldbank.org/catalog/2734 | 2026-10-16 |
| D6 | JONAPWD Assumptive Data 2025 PDF downloaded; licence notice | ◐ | Downloaded to `data/sources/jonapwd/` (git-ignored): 5,980,855 bytes, SHA-256 `c861f33cdfd8ed79e83598acb853dc2295667b9d169cd511e4beb1a54d638732`, 50 pages. Web page footer: "© 2021 JONAPWD. All rights reserved." No open licence: cite the figures as facts and ask JONAPWD before redistributing the PDF. The PDF's own notice is not yet checked. | https://jonapwdng.org/10865-2/ | 2026-10-16 |
| D7 | JONAPWD PDF confirmed scanned (no text layer) → OCR needed | ✗ | **Contradicts the plan.** The PDF has a text layer (~29k characters; Producer iLovePDF). Pages 14–50 are per-state Power BI exports with values in the text. Only pages 1, 9, 10, 13 carry images. Text extraction is enough, with no OCR; the label-to-value mapping must still be hand-validated. | local file, pypdf 5.4.0 | 2026-10-16 |
| D8 | NBS Demographic Bulletin 2023 has state projections usable as denominators | ☑ | Datasheet Annex 3 gives 2023 projections by state × sex (37 units). They sum to 221,250,127 (M 112,434,239; F 108,815,888), equal to Annex 1, and M+F=T on every row. State names are inconsistent ("Abia state", "Cross river", "FCT Abuja"), so they need the alias seed. In Annex 2, Excel turned some age bands into dates. Stored git-ignored in `data/sources/nbs-demographic-2023/`; catalog says "All Rights Reserved", so cite it and don't redistribute. | https://microdata.nigerianstat.gov.ng/index.php/catalog/182 | 2026-10-16 |
| D9 | WorldPop licence (CC BY 4.0) and the product used | ☑ | Nigeria v3.0 README: "may be redistributed following the terms of a Creative Commons Attribution 4.0 International (CC BY 4.0) license". The release includes `NGA_population_v3_0_table.zip` with `state_pop_total_scaled.csv` and LGA totals, scaled to UN WPP 2025. That is the state-level cross-check. Citation: Nnanatu et al. (2025), doi:10.5258/SOTON/WP00782. | https://data.worldpop.org/repo/wopr/NGA/population/v3.0/NGA_population_v3_0_README.pdf | 2026-10-16 |
| D10 | geoBoundaries Nigeria ADM1 licence | ☑ | CC BY 4.0; source GRID3, boundary year 2022; 37 units (36 states + FCT). | https://www.geoboundaries.org/api/current/gbOpen/NGA/ADM1/ | 2026-10-16 |

## LLM quotas (record what the console actually shows)

| # | Item | Status | Result | Source | Checked |
|---|---|---|---|---|---|
| L1 | Gemini Flash free tier: RPM / RPD / TPM for the model used | ◐ | Google does not publish the numbers; the docs say limits are shown in AI Studio. Nigeria is a supported region. Read the actual limits from AI Studio once an account exists. | https://ai.google.dev/gemini-api/docs/rate-limits | 2026-10-16 |
| L2 | Gemini free tier: are prompts used for training? | ☑ | Yes: on unpaid services, content may be used to improve Google products and ML, and may be read by human reviewers. Send only public aggregates. | https://ai.google.dev/terms | 2026-10-16 |
| L3 | Groq free tier: RPM / RPD / TPM for the model used | ◐ | Official page: gpt-oss-120b 30 RPM / 1K RPD / 8K TPM / 200K TPD. Third-party sources give llama-3.1-8b-instant 30 RPM / 14.4K RPD / 6K TPM / 500K TPD (unconfirmed). Check console.groq.com/settings/limits. | https://console.groq.com/docs/rate-limits | 2026-10-16 |

## WCAG 2.2 criteria wording (quote the normative text)

| # | Criterion | Status | Wording | Source | Checked |
|---|---|---|---|---|---|
| W1 | 1.1.1 Non-text Content | ☑ | (A) All non-text content presented to the user has a text alternative serving the equivalent purpose (exceptions: controls, time-based media, CAPTCHA, decoration). | https://www.w3.org/TR/WCAG22/ | 2026-10-16 |
| W2 | 1.4.3 Contrast (Minimum) | ☑ | (AA) Text and images of text at least 4.5:1; large text 3:1; inactive components, decoration and logotypes exempt. Relative luminance uses the 0.04045 threshold (formerly 0.03928, no practical difference), which matches `contrast.py`. | https://www.w3.org/TR/WCAG22/ | 2026-10-16 |
| W3 | 1.4.11 Non-text Contrast | ☑ | (AA) UI components and graphical objects needed to understand the content: at least 3:1 against adjacent colours. | https://www.w3.org/TR/WCAG22/ | 2026-10-16 |
| W4 | 2.1.1 Keyboard | ☑ | (A) All functionality operable through a keyboard interface without specific keystroke timing, except functions that depend on the path of movement. | https://www.w3.org/TR/WCAG22/ | 2026-10-16 |

## Repo bootstrap

| # | Item | Status | Checked |
|---|---|---|---|
| R1 | uv workspace, ruff, pyright, pytest pass locally (Python 3.12.13) | ☑ | 2026-10-16 |
| R2 | renv 1.3.0 initialised (R 4.5.2, explicit snapshots); `renv.lock` committed | ☑ | 2026-10-16 |
| R3 | pre-commit installed; restricted-zone guard blocks a staged `data/restricted/` file | ☑ | 2026-10-16 |
| R4 | GitHub repo `curb-cut` created (public); CI green on `main` (run 38858560202) | ☑ | 2026-10-16 |

## Findings that affect the plan

- **D7 (✗): the JONAPWD PDF needs no OCR.** P1 and P3 can use text extraction (pdfplumber/pypdf) plus hand validation instead of docling/Tesseract.
- **New candidate source: Nigeria DHS 2024** (NG2024DHS, released 2025-10-20). Its household-member file carries the full Washington Group Short Set (hdis2–hdis9). The World Bank catalog (8029) only links out: access goes through dhsprogram.com (account plus project request), and registration is open again. It could be a second prevalence source next to MPI 2021, not only a published-table benchmark.
- **D2 (✗, in our favour): GHS-Panel W4 already has all six WG-SS questions.** An exploratory onset analysis can use W4→W5 across all six domains, not just W3→W5 seeing/walking. **Checked 2026-10-17 on the downloaded files:** the same 4 response categories in both waves (W4 adds −1 "too young"). 4,735 households are in both waves (W4 4,979; W5 4,771). Among matched households, 98.2% have the same state and 96.6% the same EA.

## P0 gate

- [ ] CI green
- [ ] Every row above confirmed or marked ✗ with a decision recorded in `PLAN.md`
- [ ] Author review
