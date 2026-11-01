---
title: "Disability and poverty in Nigeria"
subtitle: "Policy brief from Curb Cut. Results of 1 November 2026."
lang: en-NG
---

## Key finding

**People in households with a member aged 5 or older who has a severe difficulty are 11.7 percentage points more likely to be multidimensionally poor than people in comparable households (95% confidence interval 6.1 to 17.2 points).** In comparable households without such a member, 62.9% of people are multidimensionally poor. With the difference added, the figure for households with such a member is 74.6%.

Exposure is rare, so the main estimate leans on few households. Among households where the
comparison is better supported (those whose estimated chance of having such a member was
between 0.01 and 0.99, 38.3% of people), the difference
is 8.1 points (95% confidence interval
2.1 to 14.1). Both estimates are shown with equal weight.

## What this does and does not show

This is **an adjusted association, not a causal effect**. It does not show that disability
makes households poorer. Two reasons:

1. Poverty can come first. Earlier poverty can lead to disability, for example through poor nutrition, unsafe work or little health care, and earlier poverty also goes with poverty today. A survey at one point in time cannot tell which came first.
2. Some shared factors were not measured. Religion, ethnicity, conflict, local health services and the household's earlier poverty are not in the survey, and a factor like these could account for part or all of the difference. [How strong such a factor would need to be](https://batestguy.github.io/curb-cut/poverty.html#sensitivity-heading).

A hidden factor would not need to be strong: one accounting for 1.8% of what is
left unexplained in both poverty and in which households have such a member could bring the
estimate to zero (E-value 1.66). But a factor as strong as any measured one
(the head's education, place, or urban or rural) would move it only to between
10.7 and 12.7 points.

Who counts as having a severe difficulty comes from MPI's own disability questions (not the Washington Group's DISABILITY3 measure). For seeing, hearing and walking, the survey asks how hard it is only of people who said yes to a difficulty and use glasses, a hearing aid or walking equipment. People who said yes but have no aid were not asked, and here they count as not severe. Aids cost money, so this probably puts some severely disabled people from poorer households in the comparison group; the pre-registration expected this to pull the estimate towards zero. Counting all of them as severe instead (secondary question S5, 4,086 households with such a member) gives 5.4 points (95% confidence interval 1.5 to 9.7). The pre-registration treats the two definitions as two bounds. S5's group is much larger and includes people whose difficulty was never graded, so many of them may have only some difficulty.

## How it was checked

The plan was registered publicly before any poverty figure was split by disability
(https://osf.io/kes3p/, 2026-11-01 05:49:21 UTC),
with no deviations so far. Our rebuilt index reproduces NBS's published comparison (Table 7:
72.0% against NBS's
71.4% poor with a person with a disability,
61.8% against
61.8% without; the check passed). Eight other
reasonable choices give 10.1 to
13.0 points; leaving out one zone at a time gives
9.3 to 12.7.
Shuffling exposure 100 times gave estimates centred near zero,
and a random extra factor moved the estimate by only
0.34 points (check passed). A survey-weighted linear
model gives 8.0 points (3.4 to 12.6).

## Other registered results

- NBS's broad definition (S2): 6.8 points (3.5 to 10.2). The
  household head has the difficulty (S3): 10.2 points (4.1 to 16.4).
- Where the difference sits (S4, points out of 100 on the deprivation score): health
  2.0 (0.9 to 3.2), work and shocks
  1.3 (0.5 to 2.2), education
  0.4 (-0.2 to 1.0), living standards
  0.3 (-0.5 to 1.0). Descriptive only.
- **Exploratory** (the same people in 2018/19 and 2023/24, General Household Survey-Panel):
  among 10,933 people with no severe difficulty in 2018/19,
  364 had one by 2023/24. Work: -26.4 percentage
  points (-33.2 to -19.7): the share who worked went down by more, or up by less, among people whose severe difficulty began between the rounds than among comparable people without onset. Consumption:
  0.035 log points
  (-0.045 to 0.114): the interval includes zero, so the survey cannot show a difference in consumption. Two rounds only; the comparison
  assumes the two groups would otherwise have changed alike, which cannot be tested.

## What this suggests for policy

- **Find these households.** Multidimensional poverty is more common in households with a
  severely disabled member. Poverty programmes and social registers can record disability,
  with the Washington Group questions, so that these households can be reached.
- **Ask everyone the severity questions.** MPI 2021 asked how hard seeing, hearing or walking
  is only of people who use an aid. Asking the Washington Group Short Set of every member
  aged 5 and over would close the main measurement gap found here.
- **Read the number as a description.** It shows where poverty is concentrated, not what
  would happen if disability were prevented or supported. Policies should be judged on their
  own evaluations.

## Data, registration and citations

- Full results, checks and explanations: https://batestguy.github.io/curb-cut/poverty.html
- Pre-registration: https://osf.io/kes3p/ (frozen at tag
  p5-freeze, commit
  22b8acee10b304f25201627d5cf4da47c2544a19).
- National Bureau of Statistics, Multidimensional Poverty Index Survey 2021, v1.0
  (NGA-NBS-MPI-2021-v1.0); NBS, Nigeria Multidimensional Poverty Index (2022), Table 7.
  Aggregated reporting only; a copy of this brief goes to the National Data Archive.
- NBS and the World Bank, General Household Survey-Panel, Waves 4 (NGA_2018_GHSP-W4_v03_M)
  and 5 (NGA_2023_GHSP-W5_v02_M), World Bank Microdata Library.
- Curb Cut's disability prevalence figures elsewhere use the Nigeria Demographic and Health
  Survey 2024 (National Population Commission and ICF, The DHS Program); no DHS data are used
  in this brief.
- Only estimates that passed a disclosure check (at least 30 households or people in each
  group) are published.
