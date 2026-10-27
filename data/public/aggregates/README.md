# Survey aggregates

Weighted disability estimates from licensed survey microdata. Every file here was written by the disclosure gate (`packages/ingest/src/curbcut_ingest/disclosure.py`), the only code that writes to this folder. The microdata never leave the git-ignored `data/restricted/`. `manifest.json` records, per file, the source and dataset version, the terms of use, the SHA-256, the commit of the scripts that produced it, the disclosure threshold, the number of suppressed cells and the precision flags.

**Not shown on the site yet.** These are the first aggregates (P3). They go on the site in P4.

How to rebuild them from your own copy of the microdata: `docs/reproduce.md`.

## Files

| File | Source | Rows | Suppressed | Contents |
|---|---|---|---|---|
| `dhs2024_state.csv` | Nigeria DHS 2024 | 5,138 | 168 | DISABILITY3 and each of the six domains at "a lot of difficulty" or worse, by state (37), for ages 18+ and 5–17: overall, by sex, by urban/rural and by wealth quintile |
| `dhs2024_national.csv` | Nigeria DHS 2024 | 197 | 0 | National, ages 18+ and 5–17: DISABILITY3, each domain at 3+, the 4-level distribution per domain; DISABILITY3 and domains by sex, urban/rural and wealth quintile; DISABILITY3 by age band |
| `dhs2024_zone.csv` | Nigeria DHS 2024 | 894 | 0 | By zone (6), ages 18+ and 5–17: DISABILITY3 and domains overall, by sex, urban/rural and wealth quintile; DISABILITY3 by age band |
| `ghs_w4_national_zone.csv` | GHS-Panel W4 (2018/19) | 13 | 0 | Adults 18+: national DISABILITY3 and domains; DISABILITY3 by zone |
| `ghs_w5_national_zone.csv` | GHS-Panel W5 (2023/24) | 13 | 0 | As W4 |
| `mpi2021_state_national.csv` | NBS MPI 2021 | 532 | 0 | MPI's own measures (never DISABILITY3) by state and nationally; released 2026-10-24 |

GHS is representative only nationally and by zone, so it never has state rows.

## Columns

| Column | Meaning |
|---|---|
| `source`, `dataset_version` | `dhs2024`, `ghs_w4`, `ghs_w5` (and `mpi2021` when published), with the microdata release used |
| `measure` | See below |
| `geography_level`, `geography` | `national` (`NG`), `zone` (zone name), or `state` (ISO 3166-2 code, e.g. `NG-KN`; names in `packages/transform/seeds/dim_states.csv`) |
| `age_group` | `18+` (the headline) or `5-17` (reported separately) |
| `sex` | `all`, `male` or `female` |
| `breakdown` | `all` (no extra dimension), `sector` (urban/rural), `wealth_quintile` or `age_band` (DHS only) |
| `breakdown_level` | `all` when `breakdown` is `all`; else `urban`/`rural`; `lowest`, `second`, `middle`, `fourth`, `highest`; or an age band (`5-9`, `10-14`, `15-17` inside 5–17; `18-29`, `30-39`, `40-49`, `50-59`, `60-69`, `70+` inside 18+). Age bands are DISABILITY3 only, national and zone only |
| `estimate` | Weighted proportion, 0–1 |
| `se` | Standard error (Taylor linearisation, R `survey`) |
| `ci_low`, `ci_high` | 95% Korn–Graubard interval: Clopper–Pearson with the effective sample size scaled by (t<sub>n−1</sub> / t<sub>df</sub>)² |
| `n_unweighted` | Respondents in the denominator (the cell's population with the item answered) |
| `n_effective` | p(1−p)/se², capped at `n_unweighted` (NCHS) |
| `df` | Design degrees of freedom: PSUs with a respondent in the cell minus their strata |
| `precision_flag`, `precision_reason` | NCHS Data Presentation Standards for Proportions (below), or `suppressed` |
| `suppressed` | `True` when the disclosure check removed the numbers |

## Measures

- `disability3`: Washington Group Short Set DISABILITY3 (WG Doc 7A): "a lot of difficulty" or "cannot do at all" in at least one of the six domains. 0 when all six are answered and none is at that level; missing (left out of the denominator) otherwise. `docs/verification.md` D23.
- `<domain>_3plus`: the domain alone at "a lot of difficulty" or worse. Domains: `seeing`, `hearing`, `walking`, `cognition` (remembering or concentrating), `selfcare`, `communication`.
- `<domain>_level_1` … `_level_4`: share at each level (no difficulty, some, a lot, cannot do at all). National only.
- "Don't know" and, in GHS W4, "too young" are missing.
- MPI 2021 uses its own names, **never DISABILITY3**, because its module is not the WG-SS (`verification.md` D39, D43): `mpi_screener_<seeing|hearing|walking>_any` (yes to "does (name) have difficulty …?") and `mpi_<selfcare|cognition|communication|upper_body>_3plus` (communication = the worse of understanding and being understood; upper body = the worse of lifting a 2-litre bottle and using hands).

## Disclosure check and precision flag

- **Disclosure (privacy).** The rule is on the denominator: a cell with fewer than 30 unweighted respondents is suppressed (`estimate`, `se`, the interval, `n_unweighted`, `n_effective` and `df` are empty and `suppressed` is `True`). Published cells add up (wealth quintiles to their state, states to their zone and to Nigeria, women and men to both sexes, severity levels to 100%), so one suppressed cell among published siblings could be worked out by subtraction. Wherever a set of cells that add up would hold exactly one suppressed cell, its smallest other cell is suppressed too (*secondary* suppression, `precision_reason` = "complementary suppression (disclosure)"), repeated until no set does. The warehouse re-checks this (`assert_no_lone_suppressed_sibling`). One cell is source × measure × geography level × geography × age group × sex × breakdown × breakdown level. There is no rule on the numerator, which is consistent with DHS practice (DHS final-report tables apply a denominator rule, suppressing figures based on fewer than 25 unweighted cases) and with NCHS (no minimum number of events, Parker et al. 2017 p. 5). The unweighted number of people with the difficulty (`n_events`) is used inside the gate and is **never published**. The only suppressed cells are 413 state × wealth quintile cells in 16 states (168 under 30, 245 secondary); 42 possible state × quintile cells (across measures and age groups) have no respondents at all and so have no row.
- **Precision (reliability).** `precision_flag` follows the NCHS Data Presentation Standards for Proportions (Parker et al. 2017, `verification.md` D42) plus one stricter project rule:
  - `unreliable`: n or effective n under 30; or the interval is 0.30 wide or more; or it is wider than 0.05 and wider than 130% of the estimate.
  - `review`: it would be shown, but it rests on 0 events (or all events), or has fewer than 8 degrees of freedom (NCHS), or rests on 1–9 unweighted events (project rule, reason `low_events<10`).
  - `reliable`: passes the NCHS proportion standards **and** the 10-event rule. It is a screening label, not a guarantee that the estimate is accurate: the standards say nothing about measurement error, non-response or a wrong design assumption.
- The flag labels estimates; it does not remove them. `precision_reason` gives the rule that fired.
- Current files: `dhs2024_state.csv` 789 reliable, 3,761 review, 175 unreliable, 413 suppressed (the 518 overall cells: 183 reliable, 335 review, as before; by wealth quintile most cells are review or unreliable, and even DISABILITY3 18+ is reliable in only 82 of 183 state × quintile cells, with 30 suppressed); `dhs2024_national.csv` 192 reliable, 5 review (`low_events<10`); `dhs2024_zone.csv` 526 reliable, 361 review, 7 unreliable; both GHS files all 13 reliable; MPI 192 reliable, 340 review. Many state-by-domain cells are `review` because single-domain difficulty at level 3+ is rare: read them with their intervals.

## Design and assumptions

- **DHS 2024:** de facto household members aged 5+ asked the WG-SS (`hdis2`–`hdis8`); weight `hv005`/10⁶, strata `hv023`, PSU `hv021`. Urban/rural is `hv025`; wealth quintile is the DHS combined wealth index `hv270` (1 poorest … 5 richest, published as `lowest` … `highest`).
- **GHS W4/W5:** members 5+; cross-section household weights (`wt_wave4`, `wt_cross_wave5`); strata `strata`; PSU `cluster`. A few households sit in a stratum other than their zone, so a zone estimate can touch a stratum with one PSU; R reports these and adjusts them (below).
- **MPI 2021:** person weight `pop_wgt / hhsize` (the household weight with a per-state calibration factor, checked from the data); strata state × senatorial district × sector and PSU = EA, an assumption since no strata variable is shipped (`verification.md` D40).
- **Lonely PSUs:** `options(survey.lonely.psu = "adjust", survey.adjust.domain.lonely = TRUE)`.

## Terms and citation

- DHS: The DHS Program, Nigeria DHS 2024 (NPC and ICF). Data used only for the registered project "Curb Cut: disability prevalence and poverty in Nigeria"; a PDF of every publication goes to references@dhsprogram.com.
- GHS-Panel: National Bureau of Statistics, Nigeria, General Household Survey-Panel W4 (NGA_2018_GHSP-W4_v03_M) and W5 (NGA_2023_GHSP-W5_v02_M), World Bank Microdata Library.
- Full citations are in `manifest.json`.
