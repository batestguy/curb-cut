# Reproduce the survey aggregates from licensed microdata

This takes a researcher with their **own** access to the NBS, DHS and World Bank microdata from the raw Stata files to every file in `data/public/aggregates/`. The microdata never leave your machine: everything below reads from and writes to the git-ignored `data/restricted/`, and only the disclosure gate writes to `data/public/aggregates/`.

You cannot get the microdata from this repo. Register and request them yourself, and keep to each provider's terms (below).

## 1. Get the microdata

| Survey | Where | Release used |
|---|---|---|
| NBS MPI 2021 | https://microdata.nigerianstat.gov.ng/index.php/catalog/71 (public use, by request) | NGA-NBS-MPI-2021-v1.0 |
| Nigeria DHS 2024 | https://dhsprogram.com/data/dataset/Nigeria_Standard-DHS_2024.cfm (DHS account plus a project request) | NG2024DHS, recode 8B: household member recode `NGPR8BDT.zip` (Stata) |
| GHS-Panel W4 | https://microdata.worldbank.org/index.php/catalog/3557 | NGA_2018_GHSP-W4_v03_M (Stata 12) |
| GHS-Panel W5 | https://microdata.worldbank.org/index.php/catalog/6410 | NGA_2023_GHSP-W5_v02_M (Stata) |

Terms in short: aggregates only; no redistribution of the microdata, in any form or tool; no attempt to identify anyone. NBS asks for an electronic copy of every publication for the National Data Archive. DHS data may be used only for the project you registered, and DHS asks for a PDF of every publication (references@dhsprogram.com).

## 2. Put the files where the scripts expect them

Unzip so that these paths exist (relative to the repo root). The SHA-256 values are the ones in this project's local `MANIFEST.md` files; check yours with `sha256sum <file>` (Git Bash, Linux, macOS) or `Get-FileHash <file>` (PowerShell). A different hash means a different release: the scripts may still run, but the numbers will not match the published ones.

| Path | SHA-256 |
|---|---|
| `data/restricted/nbs-mpi-2021/_data/SECTION A _ IDENTIFICATION.dta` | `15b8d5e6e28e12ac0b8ed5f0a9933e7956604d2b8adfc98379108b88f14a13e5` |
| `data/restricted/nbs-mpi-2021/_data/SECTION B-DEMOGRAPHIC CHARACTERISTIC.dta` | `3d727bebb8bc773103ac9f76b709858194864742ae4ffa9612b7bbb70275e7e2` |
| `data/restricted/nbs-mpi-2021/_data/SECTION D_ DISABILITY FOR 5 YEARS AND ABOVE.dta` | `64f20b511eefa8d0e7020a19cd7d575f7b2fcecf1ebb3dafaa740362971570e2` |
| `data/restricted/dhs-2024/pr/NGPR8BFL.dta` | `7e205df03b75a3b1e1ae30e87040c7afd240dfed903fc62898c76574be1c4190` |
| `data/restricted/ghs-w4/sect4a_harvestw4.dta` | `714ee32240cb84c3d81d81994ba11b29cff3235d1ba4d0a02fcfb3ecb4bd2b0a` |
| `data/restricted/ghs-w4/sect1_harvestw4.dta` | `887945a36f3db026b02232496a54416547e32f029898ab656c539294e90b0b14` |
| `data/restricted/ghs-w4/secta_harvestw4.dta` | `83b2bd91bda50444f666fc87add87899fb34ddc6674f04b5e34faca868a88b2e` |
| `data/restricted/ghs-w5/Post Planting Wave 5/Household/sect3_plantingw5.dta` | `3172419843bc2f95a95f4bb5dafaaa793ff52ccda14ff0046d7c63103d1e8154` |
| `data/restricted/ghs-w5/Post Planting Wave 5/Household/sect1_plantingw5.dta` | `56adb38937a4bb90a9ddf2fc141aa312325611b486fee62a3155cf826586fe32` |
| `data/restricted/ghs-w5/Post Planting Wave 5/Household/secta_plantingw5.dta` | `778aa8ea03f9bd9a52e57c01addea260af102e2fc3a5154695eebf101a06c772` |

Zip hashes, for reference: MPI `a3d158a70a031aa1357d7b3d48f112d5198e5b658ad013bbc6768ca0f2403469`; DHS `NGPR8BDT.zip` `aaf472e8a17ee032a9e529330476db8fe87a2c2bda3b21768fa445ed2a503612`; GHS W4 `784cd5846c1bb2f1429d90e099e70e6e053d2210b5b8c58f85aeac13b27edb63`; GHS W5 `1689d2f6733b103197e3984d937f9e4a61981921feaede571c1666fb35c0971d`.

`data/restricted/` is in `.gitignore`, and a pre-commit hook refuses any file under it. Do not change either.

## 3. Install the tools

- Python 3.12 and [uv](https://docs.astral.sh/uv/): `uv sync` from the repo root (installs `curbcut-ingest` with pyreadstat, pandas, pyarrow).
- R 4.5 with renv: start R in the repo root and run `renv::restore()` (installs `survey`, `nanoparquet`, `jsonlite` at the versions in `renv.lock`). If `Rscript` is not on your `PATH`, set `RSCRIPT` to its full path.

## 4. Harmonise (microdata → person-level Parquet, still restricted)

From the repo root:

```
uv run python -I -m curbcut_ingest.restricted.dhs2024
uv run python -I -m curbcut_ingest.restricted.mpi2021
uv run python -I -m curbcut_ingest.restricted.ghs
```

Each reads only the columns it needs and writes `data/restricted/derived/<source>.parquet` (`dhs2024`, `mpi2021`, `ghs_w4`, `ghs_w5`). They print only row counts and match rates, with any count under 30 shown as "<30", and never print a value or an error message (which could quote one). The rules each applies (who is in scope, missing codes, MPI routing, design variables) are in the module docstrings in `packages/ingest/src/curbcut_ingest/restricted/` and summarised in `data/public/aggregates/README.md`.

Counts you should see with the releases above: DHS 148,177 people (de facto, aged 5+, asked the module); MPI 213,820; GHS W4 23,280; GHS W5 24,439.

## 5. Estimate, gate and publish

```
uv run python -I -m curbcut_ingest.aggregate
```

For each source this adds the 0/1 indicators, runs `packages/ingest/R/estimate.R` (R `survey`: weighted proportions, Taylor-linearised SEs, Korn–Graubard intervals, design df), keeps the raw cells in `data/restricted/derived/estimates/`, then passes them through the disclosure gate (`curbcut_ingest.disclosure`): cells under 30 unweighted respondents are suppressed, every row gets the NCHS precision flag, and `data/public/aggregates/manifest.json` is updated with each file's SHA-256 and the script commit. One source at a time: `--sources dhs2024` (choices `dhs2024`, `ghs_w4`, `ghs_w5`, `mpi2021`).

**Check:** your CSVs should have the same SHA-256 as `manifest.json` → `files`. Different R or package versions can change the last printed digit of an estimate; the row counts, suppression counts and flags should still agree.

## 5a. Validate against the published report and a second implementation (DHS)

```
uv run python -I -m curbcut_ingest.validate_ndhs
uv run python -I -m curbcut_ingest.crosscheck_svy
```

`validate_ndhs` recomputes NDHS 2024 Tables 14.1, 14.2.1 and 14.2.2 from the PR file on the report's own conventions and compares them with the transcription in `data/public/ndhs_report/`; every cell should match to the published decimal (exit 0). It counts 148,226 people: the 148,177 above plus 49 whose age is "don't know", whom the report counts as 15+. `crosscheck_svy` re-estimates every published DHS state cell with Python `svy` and compares it with the R output: estimates equal, SEs within 5% (in practice under 0.5%). Both print only the comparison, never a recomputed cell on its own. Results: `docs/verification.md` D48.

## 6. Load into the warehouse and test

```
cd packages/transform
uv run dbt deps --profiles-dir .
uv run dbt build --profiles-dir .
uv run dbt build --profiles-dir . --vars '{include_mpi: false}'  # optional: leave MPI 2021 out
```

The tests re-check the disclosure rule (no unsuppressed cell under 30), that every row has a precision flag, that all 37 states resolve, that estimates and intervals lie in [0, 1] with `ci_low ≤ estimate ≤ ci_high`, that GHS has no state rows and that MPI is never labelled DISABILITY3.

## Denominators (optional)

The state × sex 2023 seed `packages/transform/seeds/state_population_by_sex_2023.csv` was copied from the NBS Demographic Bulletin 2023 datasheet (Annex 3, https://microdata.nigerianstat.gov.ng/index.php/catalog/182; "All Rights Reserved", so the file is not in the repo). With the xlsx at `data/sources/nbs-demographic-2023/Demographic Bulletin Datasheet.xlsx`:

```
uv run python -I -m curbcut_ingest.nbs_annex3
```

It checks that males + females equal the total on every row, that the states sum to the Nigeria row, and that the totals equal `state_facts.population_2023`, before writing the seed.
