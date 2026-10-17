# JONAPWD 2025 per-state figures

`state_disability_type.csv` holds the per-state, per-type figures published by the Joint National Association of Persons with Disabilities (JONAPWD), 370 rows (37 states × 10 types). `manifest.json` is written by the extraction script and records the hash, date and cross-checks.

**These are assumption-based figures, not survey estimates.** JONAPWD applied the global 15% disability benchmark to population projections and then split the result by type. Treat them as JONAPWD's estimates, not as measured prevalence.

## Source

- Publication: JONAPWD, *2025 Assumptive Disability Disaggregated Data*. © JONAPWD. All rights reserved.
- PDF: https://jonapwdng.org/wp-content/uploads/2026/03/2025-Assumptive-Disability-Disaggregated-Data-2.pdf
- Publisher page: https://jonapwdng.org/10865-2/
- PDF SHA-256: `c861f33cdfd8ed79e83598acb853dc2295667b9d169cd511e4beb1a54d638732` (50 pages)

The figures are cited as facts with attribution. The PDF itself is not redistributed: it stays git-ignored in `data/sources/jonapwd/`.

## Columns

| Column | Meaning |
|---|---|
| `state` | State name exactly as printed on the page title (e.g. `CROSS-RIVER`, `FEDERAL CAPITAL TERRITORY`) |
| `disability_type` | snake_case code: `physical`, `hearing`, `visual`, `leprosy`, `albinism`, `spinal_cord_injury`, `intellectual`, `others`, `deaf_blindness`, `little_stature` |
| `disability_type_label` | Full category label as JONAPWD prints it, untruncated |
| `persons` | Number of persons, as printed |
| `source_page` | PDF page (1-based) the row came from |

## Method

Extracted on 2026-10-16 with `packages/ingest` (`uv run python -I -m curbcut_ingest.jonapwd <pdf>`), from the PDF's text layer with pdfplumber. No OCR.

Pages 14–50 are Power BI exports, one per state. 20 use vertical bars and 17 horizontal bars, and each sorts its bars by value, so text order cannot tell which value goes with which category. The script maps them by geometry instead. Each value is printed at the end of its bar, and the category label sits beside the bar's base on the same axis. Horizontal pages truncate labels with an ellipsis (`PERSONS WITH HEARI…`); the script resolves those by unique prefix. As an independent check on every page, bar lengths must be proportional to the values within 2%. The script refuses to write anything if a page breaks any of these rules or the PDF hash differs.

## Hand validation

Pages were rendered to PNG (pypdfium2, not committed) and compared by eye with the CSV:

- **State pages 14 (Abia), 19 (Bayelsa), 20 (Benue), 28 (FCT), 38 (Lagos), 44 (Oyo), 50 (Zamfara):** all 70 values matched, including ties (Benue, FCT, Lagos, Oyo), a value printed inside its bar (Benue, Zamfara) and both layouts.
- **Page 11 (national donut, in thousands):** each per-type sum of the CSV rounds to the printed figure for its legend colour (physical 8,187K; hearing 7,653K; visual 7,188K; leprosy 2,818K; albinism 2,782K; spinal cord injury 2,532K; intellectual 2,488K; others 1,101K; deaf-blindness 91K). Little stature (61,511) has no printed label on the donut.

## Cross-check with page 10

Page 10 has a scrolled table of state totals. Only 32 states are visible (Abia to Plateau), plus a grand total of 34,901,403.

- The CSV sums to 34,901,406, which is 3 more than the printed total.
- For 22 of the 32 visible states, the sum of the ten types differs from the printed total by 1–3 persons. The rest match exactly. This looks like rounding in JONAPWD's own per-type split, so the values are kept as printed and not adjusted. `manifest.json` lists every difference.
