# Fay-Herriot covariates (P4a step 2)

Written 2026-10-28, **before any model is fitted** (`PLAN.md` → P4a step 2). Nothing below has been looked at against the outcome. This file is the record that the candidate list and the selection rule came first. Status: **approved by the author on 2026-10-28** (all five covariates and the selection rule, unchanged). The covariates and the rule are frozen as of that date.

## Outcome

DHS 2024 DISABILITY3, adults 18+, both sexes, by state: `data/public/aggregates/dhs2024_state.csv`, `measure = 'disability3'`, `age_group = '18+'`, `sex = 'all'`, `breakdown = 'all'`. There are 37 direct estimates. All 37 are `reliable`, with CVs from 10% to 27% (median 16%).

## Candidates

All covariates are state level and public, and none comes from the NDHS 2024 sample. A covariate estimated from the same sample as the outcome has correlated sampling error, which the Fay-Herriot model assumes away. GRID3 health facilities are excluded on purpose: step 3 tests them against need.

| # | Covariate | Source | Year | Licence | How it is built | Why it might predict disability | D-row |
|---|---|---|---|---|---|---|---|
| C1 | Share of population aged 60+ | WorldPop, "Nigeria 100m Age structures", constrained, UN-adjusted (Bondarenko et al., doi:10.5258/SOTON/WP00699) | 2020 | CC BY 4.0 (stated on the hub page) | Zonal sums of the age-sex rasters over the geoBoundaries ADM1 polygons: bands 60–80+ for both sexes, divided by all bands | Disability rises steeply with age | D50 |
| C2 | Urban share of population | JRC GHSL GHS-SMOD R2023A with GHS-POP R2023A (Schiavina et al. 2023) | 2020 epoch | To confirm: the AWS registry says CC BY 4.0, while the JRC page cites Decision 2011/833/EU | Share of GHS-POP in SMOD classes 21–30 (Degree of Urbanisation level 1: towns, semi-dense areas and cities) | Access to care and the type of work differ between urban and rural areas | D51 |
| C3 | MPI poverty headcount (H) | NBS, "Nigeria Multidimensional Poverty Index (2022)", state table | Survey 2021–22 | NBS terms; cite figures only | Read from the report's state table and checked against the press range (Ondo 27%, Sokoto 91%) | Poverty and disability go together, in both directions | D52 |
| C4 | Literacy rate, women 15–24 | NBS/UNICEF, Nigeria MICS6 2021 Survey Findings Report, state table | 2021 | Report terms; cite figures only | Read from the report's literacy table | Proxy for education and access to services | D53 |
| C5 | Population density (log) | NBS 2023 Demographic Bulletin Annex 3 population ÷ land area of the geoBoundaries ADM1 polygons (CC BY 4.0, already committed) | 2023 | NBS: cite figures; geoBoundaries: CC BY 4.0 | Area in an equal-area projection (EPSG:6933), then log(people per km²) | Remoteness and service reach | D54 |

**Fallbacks**, used only if a source above can't be read, and recorded in its D-row:
- C3: the state MPI headcount computed from our MPI 2021 microdata, as an extra disclosure-gated aggregate. It is the same survey that produced the NBS figure.
- C4: the NDHS 2024 literacy table (FR395). It shares the outcome's sample, so the methodology note would have to say so.

**Considered and not added** (the plan names five; adding more costs degrees of freedom with 37 areas): the child dependency ratio, travel time to the nearest city, and conflict exposure (UCDP GED). Conflict is the most plausible for the North East; it is listed here so that leaving it out is a recorded choice.

## Selection rule (pre-declared)

1. Each covariate is standardised to mean 0, SD 1 across the 37 states.
2. Sampling variances are smoothed first with a generalised variance function (GVF) on the arcsine scale: the log of the direct variance regressed on the log of the effective sample size. The fitted variances are used in every model.
3. Candidate models are every subset of C1–C5 with **at most 3 covariates** (25 models plus the intercept-only model), fitted as arcsine Fay-Herriot by REML.
4. The model with the **lowest BIC** is chosen. Ties within 2 BIC points go to the model with fewer covariates.
5. The full table goes into the methodology note: every model's BIC, coefficients and the R² of the area-level fit.
6. If the chosen model fails its diagnostics (residual normality, or direct vs model estimates disagreeing where the samples are large), the next model by BIC is used and the failure is reported.
7. The covariates are frozen here. None is added or swapped after the outcome is examined. If a source fails, only its listed fallback is used.

## Then

The bias-corrected back-transform, benchmarking to the national direct estimate, parametric bootstrap MSE, spatial FH (`sae::eblupSFH`) compared on MSE/CV, and the published diagnostics, all as set out in `PLAN.md` P4a step 2.
