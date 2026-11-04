# Data

Two zones, because the NBS, World Bank and DHS licences forbid republishing household-level microdata.

- `restricted/`: **git-ignored, local only.** Licensed microdata (NBS MPI 2021, Nigeria DHS 2024, GHS-Panel W4/W5) and the harmonised person- and household-level files in `restricted/derived/`. Never commit it, and never send it to an LLM or any external service. A pre-commit hook refuses any file under it.
- `public/aggregates/`: survey aggregates written only by the disclosure gate (`packages/ingest/src/curbcut_ingest/disclosure.py`). A cell whose denominator has fewer than 30 unweighted respondents is suppressed, with complementary suppression so that it can't be recovered by subtraction; every row has an NCHS precision flag (Parker et al., 2017); `manifest.json` records source, version, terms, hash, script commit and suppression count. The MPI 2021 aggregates have been public here since 2026-10-24 (`docs/verification.md` D4). How to rebuild: `docs/reproduce.md`.
- The other `public/` folders hold public-input files (transcribed report tables, covariates, boundaries, model and spatial results). Each has a README with its contents, method, licence and citation.

CI never sees restricted data; it runs on synthetic fixtures with the same schema (`packages/transform/fixtures/`).

## Sources, licences and access

| Folder | Source | Licence or terms | Redistributed here? |
|---|---|---|---|
| `restricted/` (DHS) | Nigeria DHS 2024 microdata (The DHS Program; NPC and ICF) | Registered project only ("Curb Cut: disability prevalence and poverty in Nigeria"); no microdata in any tool or dashboard; a PDF of every publication to references@dhsprogram.com | No; aggregates only |
| `restricted/` (MPI) | NBS MPI Survey 2021, `NGA-NBS-MPI-2021-v1.0` | NBS access terms: "used solely for reporting of aggregated information"; no redistribution or re-identification; an electronic copy of every publication to the National Data Archive (D3) | No; aggregates only |
| `restricted/` (GHS) | GHS-Panel W4 and W5, World Bank Microdata Library | Public-use files under a confidentiality declaration; no copying of files, no re-identification; citation required (D5) | No; aggregates only |
| `public/aggregates/` | The three surveys above | As above; only disclosure-checked aggregates | Yes |
| `public/ndhs_report/` | NDHS 2024 final report (FR395), Chapter 14 | Report figures, cited | Transcribed figures only; the PDF is not |
| `public/covariates/` | WorldPop (CC BY 4.0), JRC GHSL (CC BY 4.0 / EU reuse policy), NBS MPI 2022 report, MICS6 2021 report, NBS 2023 Demographic Bulletin | As in its README | Derived values and transcribed figures; no source file |
| `public/worldpop/` | WorldPop Nigeria population v3.0 | CC BY 4.0 | Yes, one CSV |
| `public/geoboundaries/` | geoBoundaries gbOpen NGA ADM1 (from GRID3) | CC BY 4.0 | Yes, unchanged |
| `public/jonapwd/` | JONAPWD 2025 Assumptive Disability Disaggregated Data | All rights reserved | Extracted figures, cited; the PDF is not |
| `public/spatial/`, `public/sae/` | Derived from the files above; GRID3 health facilities v2.0 (CC BY 4.0) | As their inputs | Yes, results only |

Full citations are in each folder's README and in `docs/references.bib`.
