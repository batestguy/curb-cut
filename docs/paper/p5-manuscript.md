---
title: "Household disability and multidimensional poverty in Nigeria: a pre-registered secondary analysis"
running-title: "Disability and poverty in Nigeria"
lang: en-GB
---

**Running title:** Disability and poverty in Nigeria

## Abstract

**Aim:** To estimate how much more often people in Nigerian households that include
a member with a severe functional difficulty are multidimensionally poor than people in
comparable households without one.

**Methods:** Pre-registered secondary analysis of the National Bureau of Statistics
Multidimensional Poverty Index (MPI) Survey 2021 (51,422 households). Exposure
was a household member aged 5 or older with a lot of difficulty, or unable, in at least one
functional domain. The outcome was multidimensional poverty (deprivation score of 26% or
more), rebuilt from the survey files. A population-weighted standardised difference was
estimated with double machine learning, adjusting for place, household age structure and the
household head's sex, age and education.

**Results:** People in exposed households (680
households) were 11.7 percentage points more likely to be multidimensionally
poor (95% CI 6.1 to 17.2; p < .001) than people in
comparable households, where 62.9% were poor. Among households
with better comparison support the difference was 8.1 points
(2.1 to 14.1). The gap lay mostly in health and in work and shocks.
Other learners and adjustment sets gave 10.1 to
13.0 points; a survey-weighted linear model gave
8.0.

**Conclusions:** Multidimensional poverty is more common in households that include a person
with a severe functional difficulty (an adjusted association). Recording disability in
poverty programmes and social registers could help reach these households.

**Limitations:** This is an adjusted association, not a causal effect: earlier poverty can
lead to disability, and a hidden factor much weaker than those measured could explain the
difference if aligned with both. The survey asked severity of seeing, hearing and walking
only of aid users.

**Keywords:** functional difficulty; Alkire–Foster; double machine learning; pre-registration; social protection; sub-Saharan Africa

<!-- body -->

## Introduction

The relationship between disability and poverty is widely recognised but remains
ill-defined and under-researched (Groce et al., 2011). However poverty is defined, it is
closely related to disability (Palmer, 2011), and the two are believed to operate in a
cycle, each reinforcing the other (Banks et al., 2017). Disability also
brings extra costs of living that income-based measures miss (Mitra et al., 2017). A
systematic review of 150 studies in low- and middle-income countries found that 122 (81%)
reported a positive association between disability and a marker of poverty (Banks et al.,
2017). Studies using multidimensional measures, which count deprivations in health, education
and living standards rather than income alone, find higher deprivation among persons with
disabilities in several, though not all, countries and dimensions (Mitra et al., 2013;
Pinilla-Roncancio & Alkire, 2020; Pinilla-Roncancio et al., 2020; Trani & Loeb, 2012).

In Nigeria, evidence on disability and poverty is thin. A disability survey in Kogi and Niger
states described the circumstances of persons with disabilities in two states (Smith, 2011).
The National Bureau of Statistics (NBS) reported in its 2022 national Multidimensional Poverty
Index (MPI) that 71.4% of people in households with a person living with a disability were
multidimensionally poor, against 61.8% of people in other households (NBS, 2022, Table 7).
That comparison is unadjusted, and it uses a broad definition of disability (any difficulty,
or a skin condition such as albinism). Households that include a person with a disability may
differ from others in where they live, how old their members are and who heads them, and each
of these is linked to poverty. An unadjusted gap cannot show how much of the difference
remains once these are taken into account.

Two further problems affect studies of this kind. First, the analyst's choices (which
households to compare, which covariates to adjust for, which model to fit) can be made after
seeing the data, which inflates false positives; registering the plan in advance guards
against this (Van den Akker et al., 2021). Second, disability measures differ in their
cut-offs and in which domains they ask about, and estimates depend on those choices
(Hanass-Hancock et al., 2023; Mactaggart et al., 2021).

### Aim

This study estimates, for Nigeria in 2021–22, how much more likely people are to live in a
multidimensionally poor household when the household includes at least one member aged 5 or
older with a severe functional difficulty, compared with people in households without one
that are comparable on place, age structure and the head's characteristics.

## Methods

### Setting and design

This is a pre-registered secondary analysis of a national cross-sectional household survey.
The plan (questions, definitions, estimator, sensitivity analyses and the rule for wording
the result) was registered on the Open Science Framework (https://osf.io/kes3p/, 2026-11-01 05:49:21 UTC) using the
Secondary Data Preregistration template (Van den Akker et al., 2021), with the analysis code
frozen and tagged in the same commit, before the project ran any household-level analysis
linking poverty to disability. What was already known, including NBS's Table 7, is disclosed
in the registration. Deviations from the plan logged so far: none.

### Data

The NBS Multidimensional Poverty Index Survey 2021 (fieldwork 2021–22) is a nationally
representative household survey designed to measure the national MPI (NBS, 2022, 2023). The
analysis used the 52,022 households with a completed interview. The
exploratory panel comparison used the General Household Survey-Panel (GHS-Panel), Waves 4
(2018/19) and 5 (2023/24) (NBS, 2019, 2024). Both datasets were used under licence; only
estimates from at least 30 unweighted households or people per group were published.

### Measures

**Exposure.** A household was exposed if any member aged 5 or older had "a lot of
difficulty" or "cannot do at all" in self-care, remembering or concentrating, communication,
seeing, hearing or walking. These follow the domains of the Washington Group (WG) Short Set
(Madans et al., 2011), but they are the survey's own questions, not the WG's standard measure.
The survey asks the severity of seeing, hearing and walking only of people who report a
difficulty and use glasses, a hearing aid or walking equipment. People who reported a
difficulty without an aid have no severity answer and were counted as not severe. Because aids
cost money, this misclassification probably places some people with severe difficulties from
poorer households in the comparison group, which the plan expected to bias the estimate
towards zero. Under this definition 1.33% of people lived in exposed households. NBS's
broad definition was rebuilt to check the exposure coding: the first build gave too high a
share, and the reading of NBS's footnote on assistive devices was corrected before
registration; the corrected build gave 11.07%, against NBS's published 11.0%.

**Outcome.** Multidimensional poverty was rebuilt at household level from the survey files
following the national MPI: 15 indicators in four dimensions (health, education, living
standards, and work and shocks), with a household counted as poor if its weighted deprivation
score was 26% or more (Alkire & Foster, 2011; NBS, 2022). Every member shares the household's
status. As with the exposure, the rebuild was calibrated to NBS's published figures before
registration: two education rules were corrected after a first national check failed, and
the national headcount matches partly because some indicator differences offset one another.
The rebuilt index then reproduced NBS's Table 7 within the pre-set tolerance of 2 points:
72.0% against NBS's
71.4% poor with a person with a disability, and
61.8% against
61.8% without.

**Covariates.** State and senatorial district; urban or rural sector; the number of household
members in seven age bands matched to the MPI's eligibility ages; and the head's sex, age and
highest education. Employment, assets, housing, shocks and schooling were not adjusted for,
because disability may change them or they form part of the outcome.

### Analysis

The estimand was the population-weighted standardised difference in the probability that a
person lives in a poor household, between exposed and unexposed households, standardised to
the population distribution of the covariates. It is interpreted only as an adjusted
association. It was estimated with double machine learning (DML; Chernozhukov et al., 2018)
using the interactive regression model in DoubleML (Bach et al., 2022), with population
weights in the score, five-fold cross-fitting repeated five times, folds formed by
enumeration area, and propensity scores clipped at 0.01 and 0.99. The outcome and propensity
models were chosen from penalised logistic regression, random forest and gradient boosting by
cross-validated loss before any exposure difference was computed, preferring the simpler
model when within one standard error of the best; this rule chose
gradient boosting for the outcome and
penalised logistic regression for the propensity (the lowest loss
was random forest). Standard errors were clustered
by enumeration area, and p-values are from Wald z-tests. The plan fixed the smallest
difference of interest at 2 percentage points: a result would be called "no meaningful
difference" only if its whole interval lay within ±2 points.

Secondary questions (labelled as such) used the same estimator: the deprivation score (S1),
NBS's broad definition (S2), a household head with a severe difficulty (S3), each dimension's
contribution (S4), people not asked about severity counted as severe (S5), and only the
domains asked of everyone (S6). Holm's correction was applied across S1–S3. Pre-registered
checks were a survey-weighted linear probability model (Lumley, 2004), placebo exposures
permuted within district 100 times, a random added covariate, leaving out one zone at a time,
and eight robustness specifications. Sensitivity to unmeasured confounding used omitted-
variable bounds (Chernozhukov et al., 2022), sensemakr (Cinelli & Hazlett, 2020) and the
E-value (VanderWeele & Ding, 2017). Exploratory analyses estimated the difference within
sector and zone, and, in the panel, compared the change in household consumption and in work
between people whose severe difficulty began between 2018/19 and 2023/24 and people without
onset, by weighted least squares with clustered errors, run only if the minimum detectable
difference was at most half a standard deviation.

All analysis code, the frozen plan and the published estimates are openly available
(https://github.com/batestguy/curb-cut; https://doi.org/10.5281/zenodo.24050358). The analysis code was written with the help of an AI assistant
(Claude, Anthropic), under the author's direction; every analytic decision was fixed in the
registered plan, and the code was tested on synthetic data before the real run. The online
results page (https://batestguy.github.io/curb-cut/poverty.html) shows every estimate as a chart made with an open-source charting
library written for this project, which builds each chart's text description from the
plotted data, checks each number in the description against the data, and gives every chart
a data table for screen-reader users; the library has not yet been evaluated by regular
screen-reader users.

### Ethical considerations

This study is a secondary analysis of anonymised data collected by NBS; the
confidentiality of individual respondents is protected by law (Statistical Act 2007; NBS,
2023). The data were obtained under licence from NBS and the World Bank Microdata Library and
kept on the author's computer; only estimates and table cells from at least 30 households or
people per group were published, with further cells withheld where a hidden value could
otherwise be worked out. No new data were collected and no person was contacted, so no
separate ethical approval was sought.

## Results

### Sample

Of 52,022 households, 600 were excluded:
545 with missing poverty data
(1.1% of people) and
59 with missing disability answers
(0.2% of people); 4 had both. The primary analysis
included 51,422 households, of which 680
were exposed (Kish effective sample size 26,009). Exposure was rare: the
median estimated propensity among exposed households was
0.02, and the propensity was clipped for
62.0% of people.

Table 1 describes the two groups; it was added after registration, is descriptive only, and
its differences were not tested. People in exposed households lived in larger households
(7.3 against 6.4
members, person-weighted; a larger household is also more likely to include someone with a
severe difficulty) with more members aged 70 or over (0.4 against
0.1).
Their head was more often aged 60 or over (51.9% against
22.8%), female (19.3% against
14.2%) or without education (29.9%
against 24.1%), and they lived more often in the North
West and South South zones.

### Main result

People in households with a member aged 5 or older with a severe difficulty were
11.7 percentage points more likely to be multidimensionally poor than people
in comparable households (95% CI 6.1 to 17.2; p < .001;
Table 2). In comparable households without such a member, 62.9% of people are multidimensionally poor. Standardised to the same mix of households, the figure with such a member would be 74.6%. The risk ratio was 1.19
(1.10 to 1.27; this interval treats
the comparison rate as fixed). The whole interval lies above the smallest difference of
interest. In the households where the comparison is better supported (estimated propensity
between 0.01 and 0.99, 38.3% of people, of whom
66.8% were poor without exposure), the difference
was 8.1 points (2.1 to 14.1). This is a
different population from the primary one, not a correction of it.

All three Holm-corrected secondary results were supported: the deprivation score was
4.5 points higher out of 100 (S1), and the difference was
6.8 points under NBS's broad definition (S2) and 10.2
points when the head had the difficulty (S3). Restricting exposure to the domains asked of
everyone (S6) gave 12.4 points (6.3 to 18.9). Counting
people not asked about severity as severe (S5) gave a smaller difference,
5.4 points. Of the four dimensions, the difference lay mostly in
health (2.0 points of the deprivation score) and work and shocks
(1.3), with intervals for education and living standards that
include zero (S4).

### Checks

The survey-weighted linear model gave a lower estimate, 8.0 points
(3.4 to 12.6); it assumes a linear, additive relation with the covariates, which
the flexible learners do not. Other learners and adjustment sets gave
10.1 to 13.0 points, and
leaving out one zone at a time 9.3 to
12.7 (Table 3). The
100 placebo estimates averaged 0.6
points (standard deviation 2.7); none was as far from zero as the real
estimate (empirical p = .010). Of their intervals,
8% excluded zero, against about 5%
expected; with 100 draws this is within chance, but the standard errors, which ignore the
strata, may be slightly too small. Adding a random covariate moved the estimate by
0.3 points, within the pre-set allowance of 2.5 points
(the range across fold splits), a weak check.

### Sensitivity to unmeasured confounding

In the worst case, an unmeasured factor aligned perfectly with both poverty and exposure,
and accounting for 1.8% of what is left unexplained in each, could bring the
estimate to zero (Table 4). This is far weaker than the measured covariates: place, for
example, accounts for 7.8% (poverty) and 14.6% (exposure).
A factor as strong as the head's education, place or sector, and aligned with poverty and
exposure as each of those is, would move the estimate only to between
10.7 and 12.7 points; those
alignments are weak, so these bounds are narrow. In the linear sensemakr model, a factor three
times as strong as the head's education would bring the estimate to 2.1
points (-0.8 to 4.9). The E-value was 1.7
(1.4 for the confidence limit, which ignores uncertainty in
the comparison rate). With a base rate of about 60%, the risk ratio cannot exceed about
1.6, so E-values are small by construction here.

### Exploratory analyses

The difference was larger in urban (29.4 points,
18.2 to 40.5) than rural areas (6.7,
0.8 to 12.0); zone estimates varied and were imprecise (Table 5). No
interaction was tested. In the panel, of 15,229 people aged 15 and over in 2018/19, 13,266 were found again (87.1%). After keeping those with no severe difficulty in 2018/19 and complete answers, 10,933 could be used. 364 of them had a severe difficulty by 2023/24. Those lost to follow-up were younger (mean
age 31.9 against
37.4 years) and more often had a severe difficulty
in 2018/19 (3.2% against
2.0%). With complete work answers,
10,628 people (360 with onset) were
compared: the share who worked fell by more, or rose by less, among people with onset, a
difference of -26.4 percentage points (95% CI -33.2 to -19.7). The
interval for the change in log consumption, 0.03
(-0.04 to 0.11), includes zero, but the comparison could detect only
differences of about 0.27 log points or more
(design effect 11.0), so it cannot rule out a
moderate difference.

## Discussion

In Nigeria in 2021–22, people living with a household member who has a severe functional
difficulty were about 19% more likely, in
relative terms, to be multidimensionally poor than people in comparable households, an
adjusted association. Under NBS's broad definition, the adjusted difference
(6.8 points) was lower than the unadjusted gap (NBS:
9.6 points; this rebuild:
10.1), though its interval includes the unadjusted gap and
the two are different quantities. The narrower, severe definition gave a larger difference.
The direction agrees with studies that found higher multidimensional poverty among persons
with disabilities in several countries (Mitra et al., 2013; Pinilla-Roncancio & Alkire, 2020).
The difference lay mostly in the health and the work-and-shocks dimensions, as in NBS's own
description of these households (NBS, 2022); health also contributed most in a case-control
study in three countries (Pinilla-Roncancio et al., 2020). These dimensions are where
disability-related needs and lost work would be expected to appear. The panel's fall in work
among people with onset is exploratory: within a five-year gap, stopping work may come before
the reported difficulty as well as after it, and the work questions were worded differently
in the two rounds.

The secondary results bear on the measurement problem. Restricting exposure to self-care,
remembering and communication, which every member was asked, gave a difference close to the
primary, which is consistent with the result not resting on the aid-dependent questions.
Counting people not asked about severity as severe did not raise the estimate as the plan
expected; it lowered it. Those people answered only a yes/no question that does not separate
some from a lot of difficulty, so the group probably includes many milder cases, which would
dilute the difference. The plan's description of the primary and S5 estimates as two bounds
therefore did not hold.

The study has four strengths. The plan, including the wording of the result, was registered
before the project linked poverty to disability in any household data, and no deviation was
needed. After calibration, the rebuilt poverty measure reproduced NBS's published comparison
within the pre-set tolerance. The flexible estimator does not rest on one model, and the
result held across learners, adjustment sets and when any one zone was left out, although
the linear model and the overlap population gave lower estimates. All code and published
estimates are open, so the analysis can be re-run by anyone with licensed access to the
survey.

### Conclusions

Multidimensional poverty in Nigeria is more common in households that include a person with
a severe functional difficulty than in comparable households, after accounting for where
they live, their age structure and the head's characteristics. This is an adjusted
association.

### Implications

Recording disability in poverty programmes and the national social register, for example
with the WG questions, could help these households be found and reached; this study did not
assess how well such questions would target them. Future NBS surveys could ask the WG Short
Set of every member aged 5 and over, rather than asking severity only of aid users, which
would remove the main measurement gap in this survey. Because the result is an association,
it shows where poverty is more common, not what would follow from preventing or supporting
disability; policies need their own evaluations.

### Limitations

This is **an adjusted association, not a causal effect**, for two reasons. Earlier poverty
can lead to disability and also goes with poverty today, and a single cross-section cannot
order them. Religion, ethnicity, conflict, local health services and earlier poverty were
not measured; a factor aligned with poverty and exposure as the measured ones are would leave
a clear difference, but a factor much weaker than place, if aligned with both, could remove
it. Exposure was rare and the primary estimate relies partly on clipped propensities. The
disability questions are not the WG standard, and the routing misclassifies some people.
Household composition may itself respond to disability. The survey design's strata are not
distributed and were approximated. Holm's correction covered only S1–S3; the subgroup and
panel analyses are exploratory, the panel has two waves, lost younger people and people with
difficulties more often, and its comparison assumes the two groups would otherwise have
changed alike. Like the national MPI, the measure ignores the extra costs of disability, so
it may understate deprivation in exposed households (Mitra et al., 2017).

<!-- end body -->

## Acknowledgements

The National Bureau of Statistics and the World Bank
Microdata Library provided the survey data. The first draft of this manuscript was generated
with Claude (Claude Opus 5.5, Anthropic) from the registered plan and the published
estimates; every number in the text and tables is inserted by a script from the published
results file. The author reviewed and edited the text, and checked that every reference
exists and supports the statement it is cited for.

**Competing interests:** The author declares that they have no competing interests.

**Funding:** This research received no specific grant from any funding agency in the public,
commercial or not-for-profit sectors.

**Data availability:** The survey microdata are available from NBS and the World Bank
Microdata Library under their licences and cannot be redistributed. All published estimates,
the analysis code and the registered plan are openly available (https://github.com/batestguy/curb-cut; https://doi.org/10.5281/zenodo.24050358;
https://osf.io/kes3p/).

## References

Alkire, S., & Foster, J. (2011). Counting and multidimensional poverty measurement.
*Journal of Public Economics, 95*(7–8), 476–487. https://doi.org/10.1016/j.jpubeco.2010.11.006

Bach, P., Chernozhukov, V., Kurz, M. S., & Spindler, M. (2022). DoubleML – An object-oriented
implementation of double machine learning in Python. *Journal of Machine Learning Research,
23*(53), 1–6. https://jmlr.org/papers/v23/21-0862.html Accessed 10 November 2026.

Banks, L. M., Kuper, H., & Polack, S. (2017). Poverty and disability in low- and
middle-income countries: A systematic review. *PLOS ONE, 12*(12), e0189996.
https://doi.org/10.1371/journal.pone.0189996

Chernozhukov, V., Chetverikov, D., Demirer, M., Duflo, E., Hansen, C., Newey, W., & Robins,
J. (2018). Double/debiased machine learning for treatment and structural parameters. *The
Econometrics Journal, 21*(1), C1–C68. https://doi.org/10.1111/ectj.12097

Chernozhukov, V., Cinelli, C., Newey, W., Sharma, A., & Syrgkanis, V. (2022). *Long story
short: Omitted variable bias in causal machine learning* (NBER Working Paper No. 30302).
National Bureau of Economic Research. https://doi.org/10.3386/w30302

Cinelli, C., & Hazlett, C. (2020). Making sense of sensitivity: Extending omitted variable
bias. *Journal of the Royal Statistical Society: Series B (Statistical Methodology), 82*(1),
39–67. https://doi.org/10.1111/rssb.12348

Groce, N., Kett, M., Lang, R., & Trani, J.-F. (2011). Disability and poverty: The need for a
more nuanced understanding of implications for development policy and practice. *Third World
Quarterly, 32*(8), 1493–1513. https://doi.org/10.1080/01436597.2011.604520

Hanass-Hancock, J., Kamalakannan, S., Murthy, G. V. S., Palmer, M., Pinilla-Roncancio, M.,
Rivas Velarde, M., Tetali, S., & Mitra, S. (2023). What cut-off(s) to use with the
Washington Group short set of questions? *Disability and Health Journal, 16*(4), 101499.
https://doi.org/10.1016/j.dhjo.2023.101499

Lumley, T. (2004). Analysis of complex survey samples. *Journal of Statistical Software,
9*(8), 1–19. https://doi.org/10.18637/jss.v009.i08

Mactaggart, I., Hasan Bek, A., Banks, L. M., Bright, T., Dionicio, C., Hameed, S., Neupane,
S., Murthy, G. V. S., Orucu, A., Oye, J., Naber, J., Shakespeare, T., Patterson, A., Polack,
S., & Kuper, H. (2021). Interrogating and reflecting on disability prevalence data collected
using the Washington Group tools: Results from population-based surveys in Cameroon,
Guatemala, India, Maldives, Nepal, Turkey and Vanuatu. *International Journal of
Environmental Research and Public Health, 18*(17), 9213.
https://doi.org/10.3390/ijerph18179213

Madans, J. H., Loeb, M. E., & Altman, B. M. (2011). Measuring disability and monitoring the
UN Convention on the Rights of Persons with Disabilities: The work of the Washington Group on
Disability Statistics. *BMC Public Health, 11*(Suppl 4), S4.
https://doi.org/10.1186/1471-2458-11-S4-S4

Mitra, S., Palmer, M., Kim, H., Mont, D., & Groce, N. (2017). Extra costs of living with a
disability: A review and agenda for research. *Disability and Health Journal, 10*(4),
475–484. https://doi.org/10.1016/j.dhjo.2017.04.007

Mitra, S., Posarac, A., & Vick, B. (2013). Disability and poverty in developing countries: A
multidimensional study. *World Development, 41*, 1–18.
https://doi.org/10.1016/j.worlddev.2012.05.024

National Bureau of Statistics. (2019). *General Household Survey, Panel (GHS-Panel)
2018–2019* (NGA_2018_GHSP-W4_v03_M) [Data set]. World Bank Microdata Library.
https://microdata.worldbank.org/index.php/catalog/3557 Downloaded 16 October 2026.

National Bureau of Statistics. (2022). *Nigeria Multidimensional Poverty Index (2022)*.
https://ophi.org.uk/sites/default/files/2024-05/Nigeria_MPI_2022_report.pdf Accessed 10 November 2026.

National Bureau of Statistics. (2023). *Multidimentional Poverty index Survey 2021 v1.0*
[sic] (NGA-NBS-MPI-2021-v1.0; public use, April 2023) [Data set]. National Data Archive.
https://microdata.nigerianstat.gov.ng/index.php/catalog/71 Downloaded 16 October 2026.

National Bureau of Statistics. (2024). *Nigeria General Household Survey, Panel
(GHS-Panel) Wave 5 2023–2024* (NGA_2023_GHSP-W5_v02_M) [Data set]. World Bank Microdata
Library. https://microdata.worldbank.org/index.php/catalog/6410 Downloaded 16 October 2026.

Palmer, M. (2011). Disability and poverty: A conceptual review. *Journal of Disability Policy
Studies, 21*(4), 210–218. https://doi.org/10.1177/1044207310389333

Pinilla-Roncancio, M., & Alkire, S. (2020). How poor are people with disabilities? Evidence
based on the global multidimensional poverty index. *Journal of Disability Policy Studies,
31*(4), 206–216. https://doi.org/10.1177/1044207320919942

Pinilla-Roncancio, M., Mactaggart, I., Kuper, H., Dionicio, C., Naber, J., Murthy, G. V. S.,
& Polack, S. (2020). Multidimensional poverty and disability: A case control study in India,
Cameroon, and Guatemala. *SSM – Population Health, 11*, 100591.
https://doi.org/10.1016/j.ssmph.2020.100591

Smith, N. (2011). The face of disability in Nigeria: A disability survey in Kogi and Niger
States. *Disability, CBR & Inclusive Development, 22*(1), 35–47.
https://doi.org/10.5463/dcid.v22i1.11

Trani, J.-F., & Loeb, M. (2012). Poverty and disability: A vicious circle? Evidence from
Afghanistan and Zambia. *Journal of International Development, 24*(S1), S19–S52.
https://doi.org/10.1002/jid.1709

Van den Akker, O. R., Weston, S., Campbell, L., Chopik, B., Damian, R., Davis-Kean, P., Hall,
A., Kosie, J., Kruse, E., Olsen, J., Ritchie, S., Valentine, K. D., Van 't Veer, A., &
Bakker, M. (2021). Preregistration of secondary data analysis: A template and tutorial.
*Meta-Psychology, 5*. https://doi.org/10.15626/MP.2020.2625

VanderWeele, T. J., & Ding, P. (2017). Sensitivity analysis in observational research:
Introducing the E-value. *Annals of Internal Medicine, 167*(4), 268–274.
https://doi.org/10.7326/M16-2607

## Tables

**Table 1.** Household characteristics by exposure, primary analysis sample, Nigeria MPI Survey 2021: weighted % of people (unweighted households), or weighted mean.

| Characteristic | Exposed | Unexposed |
|---|---|---|
| Households (n) | 680 | 50,742 |
| **Zone** | | |
| North Central | 12.6 (98) | 14.4 (9,902) |
| North East | 10.2 (87) | 12.7 (8,494) |
| North West | 31.6 (136) | 28.3 (9,708) |
| South East | 12.6 (126) | 10.4 (6,694) |
| South South | 22.2 (173) | 14.9 (8,098) |
| South West | 10.8 (60) | 19.3 (7,846) |
| **Sector** | | |
| Rural | 72.6 (504) | 69.6 (36,382) |
| Urban | 27.4 (176) | 30.4 (14,360) |
| **Head's sex** | | |
| Female | 19.3 (185) | 14.2 (9,706) |
| Male | 80.7 (495) | 85.8 (41,036) |
| **Head's age (years)** | | |
| Under 30 | suppressed | 6.6 (5,927) |
| 30-44 | suppressed | 36.5 (18,522) |
| 45-59 | 32.3 (171) | 34.1 (14,158) |
| 60+ | 51.9 (385) | 22.8 (12,135) |
| **Head's highest education** | | |
| None | 29.9 (237) | 24.1 (12,886) |
| Non-formal | 9.9 (46) | 9.4 (4,406) |
| Pre-school | 0.0 (0) | suppressed |
| Primary, not completed | suppressed | 2.3 (1,239) |
| Primary completed | 21.4 (157) | 15.8 (7,624) |
| Secondary | 22.6 (127) | 32.4 (16,422) |
| Higher | 12.0 (78) | 15.8 (8,105) |
| Missing | suppressed | suppressed |
| **Household members (person-weighted mean number)** | | |
| Household members, all ages | 7.3 | 6.4 |
| Members aged 0-4 | 0.7 | 0.9 |
| Members aged 5 | 0.2 | 0.2 |
| Members aged 6-14 | 1.8 | 1.8 |
| Members aged 15-17 | 0.7 | 0.5 |
| Members aged 18-59 | 3.2 | 2.7 |
| Members aged 60-69 | 0.3 | 0.2 |
| Members aged 70+ | 0.4 | 0.1 |

*Note:* Not pre-registered; descriptive; differences not tested. Weighted by the population weight, so shares are of people and means are the household make-up seen by the average person. Cells from fewer than 30 households are suppressed, with further cells suppressed until no suppressed value can be worked out from the rest.

**Table 2.** Primary and secondary estimates: difference in the share of people who are
multidimensionally poor (percentage points; S1 and S4 on the 0–100 deprivation score),
exposed versus comparable unexposed households, Nigeria MPI Survey 2021.

| Estimate | Exposed households (n) | Difference | 95% CI | p |
|---|---|---|---|---|
| Primary: member aged 5+ with a severe difficulty | 680 | 11.7 | 6.1 to 17.2 | p < .001 |
| Primary, overlap population (secondary) | 508 | 8.1 | 2.1 to 14.1 | p = .007 |
| S1: deprivation score | 680 | 4.5 | 2.9 to 6.0 | p < .001 |
| S2: NBS broad definition | 5,269 | 6.8 | 3.5 to 10.2 | p < .001 |
| S3: household head | 404 | 10.2 | 4.1 to 16.4 | p = .001 |
| S5: not asked about severity counted as severe | 4,086 | 5.4 | 1.5 to 9.7 | p = .013 |
| S6: self-care, remembering, communication only | 442 | 12.4 | 6.3 to 18.9 | p < .001 |
| S4: health | 688 | 2.0 | 0.9 to 3.2 | p = .001 |
| S4: education | 685 | 0.4 | -0.2 to 1.0 | p = .215 |
| S4: living standards | 688 | 0.3 | -0.5 to 1.0 | p = .489 |
| S4: work and shocks | 683 | 1.3 | 0.5 to 2.2 | p = .003 |

*Note:* Population-weighted DML; standard errors clustered by enumeration area; p-values from
Wald z-tests. Holm-corrected p-values (S1–S3): S1 p < .001,
S2 p < .001, S3 p = .001.
S4–S6 are descriptive and unadjusted for multiplicity. Exposed counts differ slightly between
rows because each outcome or definition has its own missing answers.

**Table 3.** Robustness and refutation checks of the primary estimate (percentage points).

| Specification | Exposed households (n) | Difference | 95% CI |
|---|---|---|---|
| Survey-weighted linear probability model | 680 | 8.0 | 3.4 to 12.6 |
| Logistic regression for both models | 680 | 10.1 | 3.8 to 16.4 |
| Random forest for both models | 680 | 12.2 | 5.8 to 18.5 |
| Gradient boosting for both models | 680 | 10.3 | 4.7 to 15.9 |
| Without the head's education | 680 | 13.0 | 7.2 to 18.2 |
| Place and the head's sex and age only | 680 | 12.6 | 7.5 to 18.0 |
| Place as state only (no senatorial district) | 680 | 11.5 | 5.7 to 17.4 |
| Cooking fuel without charcoal | 680 | 13.0 | 7.3 to 17.9 |
| Don't-know shock answers counted as not deprived | 685 | 11.8 | 6.3 to 17.4 |
| Without the North Central zone | 582 | 12.0 | 5.8 to 18.2 |
| Without the North East zone | 593 | 10.2 | 2.5 to 17.9 |
| Without the North West zone | 544 | 10.6 | 2.1 to 19.1 |
| Without the South East zone | 554 | 11.7 | 6.1 to 17.3 |
| Without the South South zone | 507 | 12.7 | 6.3 to 19.1 |
| Without the South West zone | 620 | 9.3 | 4.3 to 14.4 |

*Note:* Robustness and leave-one-zone-out runs use one cross-fitting repetition.

**Table 4.** Sensitivity of the primary estimate to unmeasured confounding.

| Measure | Value |
|---|---|
| Robustness value, estimate to zero (RV; worst-case alignment) | 1.8% |
| Robustness value, interval to include zero (RVa) | 1.0% |
| Head's education: strength with poverty / exposure | 10.7% / 1.1% |
| Head's education: bounds at its estimated alignment (points) | 10.7 to 12.7 |
| Place (state and district): strength with poverty / exposure | 7.8% / 14.6% |
| Place: bounds at its estimated alignment (points) | 11.6 to 11.8 |
| Sector: strength with poverty / exposure | 2.0% / 0.7% |
| Sector: bounds at its estimated alignment (points) | 11.5 to 11.9 |
| sensemakr, 1× head's education (points, 95% CI) | 6.0 (3.0 to 9.1) |
| sensemakr, 2× head's education | 4.1 (1.1 to 7.0) |
| sensemakr, 3× head's education | 2.1 (-0.8 to 4.9) |
| E-value, estimate / confidence limit | 1.7 / 1.4 |

*Note:* Strengths and bounds from DoubleML's omitted-variable analysis (Chernozhukov et al.,
2022); the benchmark refits use the project's own code, which follows DoubleML's
`sensitivity_benchmark` but rebuilds the learners for the shorter set of covariates. The
sensemakr model is a weighted linear model that ignores the survey design. The E-value for
the confidence limit ignores uncertainty in the comparison rate.

**Table 5.** Exploratory estimates (percentage points; GHS-Panel consumption in log points).

| Estimate | Exposed / onset (n) | Difference | 95% CI |
|---|---|---|---|
| Urban | 176 | 29.4 | 18.2 to 40.5 |
| Rural | 504 | 6.7 | 0.8 to 12.0 |
| North Central | 98 | 0.2 | -14.6 to 15.0 |
| North East | 87 | 6.4 | -5.0 to 17.8 |
| North West | 136 | 16.9 | 10.3 to 23.1 |
| South East | 126 | 11.8 | -3.0 to 26.7 |
| South South | 173 | 7.9 | -2.9 to 18.7 |
| South West | 60 | 17.2 | -8.7 to 43.2 |
| GHS-Panel: change in work, onset vs no onset (n = 10,628) | 360 | -26.4 | -33.2 to -19.7 |
| GHS-Panel: change in log consumption per person (n = 10,933) | 364 | 0.03 | -0.04 to 0.11 |

*Note:* Exploratory: no multiplicity adjustment and no interaction test. GHS-Panel: people
aged 15 and over without a severe difficulty in 2018/19, longitudinal weights.
