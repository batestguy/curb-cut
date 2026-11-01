OSF registration text: Curb Cut P5
==================================

Template: "Secondary Data Preregistration" (Van den Akker et al. 2021).
Attach: docs/preregistration.md as frozen at tag p5-freeze (commit 22b8acee10b304f25201627d5cf4da47c2544a19).
Link:   https://github.com/batestguy/curb-cut/blob/p5-freeze/docs/preregistration.md  (works once the tag is pushed)
SHA-256 of the attached file: 65d0a4b2a3047e499f497aa8b59e5917ad74612c63fc8b2c66bd25af69e82955

Each answer below is short and points to the attached document, which is binding.
Paste each one under the template question it is headed with.


TITLE
Disability and multidimensional poverty in Nigeria: an adjusted association using the NBS MPI Survey 2021 (Curb Cut, phase P5)

DESCRIPTION
Pre-registered secondary analysis of the Nigeria Multidimensional Poverty Index Survey 2021. It estimates how much more likely people are to live in a multidimensionally poor household when the household includes a member aged 5+ with a severe functional difficulty, adjusted for place, household age structure and the head's characteristics. The result is reported as an adjusted association, not a causal effect. An exploratory two-wave GHS-Panel comparison is included. The full plan is the attached document (revision 3, approved 2026-10-31, frozen at git tag p5-freeze).


PART 1: STUDY INFORMATION

Research questions / hypotheses
See section 1. Primary question Q1: in Nigeria in 2021-22, how much more likely are people to live in a multidimensionally poor household when the household includes at least one member aged 5+ with a severe functional difficulty, compared with people in comparable households without one? We expect a positive difference (NBS's unadjusted gap is 9.6 points), but the test is two-sided. Secondary questions S1-S6 and exploratory X1 and E1 are listed in section 1. The interpretation rules, including the 2-point smallest difference of interest, are in sections 4 and 7.


PART 2: DATA DESCRIPTION

Datasets
See section 2.1. NBS Multidimensional Poverty Index Survey 2021 (NGA-NBS-MPI-2021-v1.0, NBS microdata catalogue entry 71) for the main analysis. GHS-Panel Waves 4 (2018/19) and 5 (2023/24) (NBS / World Bank LSMS-ISA) for the exploratory analysis E1.

Data availability and access
Both are licensed microdata, obtained by registered request from the NBS and World Bank microdata portals. They cannot be redistributed. Only aggregates that pass a disclosure check (no published cell from fewer than 30 unweighted respondents) are published.

Data identifiers
NGA-NBS-MPI-2021-v1.0 (https://microdata.nigerianstat.gov.ng/index.php/catalog/71). GHS-Panel: the World Bank Microdata Library entries for Wave 4 and Wave 5.

Data collection
Collected by NBS (MPI 2021, fieldwork 2021-22) and by NBS with the World Bank (GHS-Panel). The author had no role in data collection.

Codebooks
The survey questionnaires and the variable metadata published with each dataset. The variables used are named in sections 3 and 8.


PART 3: VARIABLES

Manipulated variables
None (observational data).

Measured variables
Exposure: section 3.2 (primary) and section 1 (S2, S3, S5, S6). Outcome: MPI-poor household (deprivation score at or above 26%), rebuilt from the 15 indicators, section 3.3. Confounders: section 3.4, with the causal diagram in section 3.5.

Unit of analysis
People, through their household (section 3.1). Population weights; clusters are enumeration areas.

Missing data
Section 6. Exposure missingness rules are in section 3.2.

Outliers
None of the variables are continuous outcomes that need outlier rules, except the deprivation scores (bounded 0-1) and GHS consumption (log change; section 8). No outliers are removed.

Sample size and power
About 52,000 interviewed households (section 3.1). Exposure under the primary definition: 688 households, 1.33% of people (share in section 2.2 item 9; the count from the check re-run on the frozen commit). The GHS analysis runs an outcome only if its minimum detectable effect is at most 0.5 SD (section 8).


PART 4: KNOWLEDGE OF DATA

Prior publication / prior knowledge
See section 2.2, which lists everything the author knew or computed before registration. That includes NBS's published unadjusted gap (71.4% vs 61.8%, Table 7 of the Nigeria MPI 2022 report), NBS's indicator-level comparison (section 3.6, Figure 14), an ecological state-level look at MPI headcount and DHS disability prevalence, the author's published disability aggregates from MPI 2021, DHS and GHS, the national MPI rebuild (H, A and MPI only), and the exposure check of item 9 (exposure shares only, no poverty data).

Prior work with the data
The author has analysed the disability section of MPI 2021 for state prevalence estimates (published on the Curb Cut website), and rebuilt the national MPI to check it against the published figures. No figure linking poverty to disability or to any confounder has been computed. The analysis code refuses to read the real data until this registration's URL is recorded in section 11.


PART 5: ANALYSES

Statistical models
Section 5.1: DoubleML interactive regression model (DoubleMLIRM, ATE score with survey weights, normalised IPW, propensity clipped at 0.01/0.99), 5 folds x 5 repetitions, folds by enumeration area, seed 20261030. Learners chosen by a pre-declared one-SE rule among logistic, random forest and gradient boosting. Benchmark: survey-weighted linear probability model (section 5.2).

Effect size
A standardised difference in the probability of being MPI-poor, in percentage points, with 95% confidence intervals; also the risk ratio and E-values (section 5.3).

Statistical test / inference criteria
Two-sided 95% intervals. The wording rules for "higher", "no meaningful difference" (within 2 points) and "inconclusive" are in sections 4 and 7. Holm correction across S1-S3 (section 5.5).

Sensitivity and robustness
Sections 5.3 and 5.4: DoubleML sensitivity bounds, benchmarks (head's education, place, sector), sensemakr, placebo permutations, a random common cause, leave-one-zone-out and the listed robustness runs.

Exploratory analysis
Section 8 (GHS-Panel, E1): change-score regression with longitudinal weights and EA clusters. Labelled exploratory and possibly underpowered.

Reliability and robustness of the exposure measure
The exposure build was checked against NBS's published 11.0% (S2 definition) before registration: 11.07%, pass (section 2.2 item 9).

Deviations
Any deviation from this plan is reported in a dated deviations section (section 10) alongside the results.


PART 6: STATEMENT OF INTEGRITY

The author confirms that the attached plan was written and frozen (git tag p5-freeze) before any figure linking poverty to disability or to any confounder was computed. Code was drafted with an AI assistant (Claude); every analytic decision is the author's.
