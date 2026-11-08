# Nigeria's disability numbers are an assumption. Here is what the surveys measured.

*Draft for the author's edit, 2026-11-08. Every number below is from the live site's published data or `docs/verification.md`; check them again after any edit.*

You will often hear that about 35 million Nigerians are disabled. The figure comes from the Joint National Association of Persons with Disabilities (JONAPWD), in its 2025 *Assumptive Disability Disaggregated Data*, and the publication is open about how it was made: the National Population Commission's projected population for 2025, 232,676,020, multiplied by a global benchmark of 15% (JONAPWD, 2025, pp. 5 and 7). Nobody was counted. The 35 million is an assumption.

I am a statistician in Bauchi and a wheelchair user. An assumed number is better than none when nothing else exists. But Nigeria does have measurements, and they had not been put in one place, with their uncertainty, in a form a disabled person can read with a screen reader. So I built [Curb Cut](https://batestguy.github.io/curb-cut/).

## The data

The Nigeria Demographic and Health Survey 2024 asked every household member aged 5 and over the Washington Group Short Set: six questions about difficulty seeing, hearing, walking or climbing steps, remembering or concentrating, caring for oneself, and communicating. It is the international standard for disability statistics in surveys.

The microdata are licensed. Its terms, like those of the National Bureau of Statistics surveys I also use, forbid publishing household-level records, so the records never leave my computer and are never sent to any online service. What the site publishes are survey-weighted estimates, and only those that pass a disclosure check: a cell with fewer than 30 respondents is suppressed, along with any cell that would let it be recovered by subtraction.

## The method

- **Survey weights and confidence intervals.** Every estimate uses the survey's sampling weights and design, computed in R's `survey` package and cross-checked in Python. Every figure comes with its 95% confidence interval and a precision flag.
- **Reproducing the official tables first.** Before publishing anything new, my code reproduces 1,360 cells of the official NDHS report.
- **Honest comparisons.** Comparing 37 states produces many comparisons, and some will look different by chance. The site counts every comparison it makes and corrects for them (Benjamini and Hochberg's false discovery rate). It only says one state is higher than another when the survey can show it.
- **What was tried and dropped.** A small-area model meant to sharpen the state figures failed the checks I set in advance, so the site does not use it.

## What the survey measured

**3.0% of adults aged 18 and over (95% confidence interval 2.8% to 3.2%) have a lot of difficulty with, or cannot do at all, at least one of the six activities.** That is the Washington Group's cut-off. The official NDHS report also publishes a broader count, *any* difficulty at all, among people aged 15 and over: 15.5%.

So is it 3% or 15%? Neither number is wrong; they count different things. The 3% counts people with serious difficulty in a core activity. The broader 15.5% includes "some difficulty", for example people who need glasses to read. The 15% behind the 35 million is neither: it is a global benchmark applied to a projection, not a Nigerian measurement.

The states are not alike. The highest estimate is Taraba's, 11.3%; the lowest is Lagos's, 0.8%. After correcting for the number of comparisons, 7 states are clearly above the national figure and 12 clearly below. But many differences are too small for the survey to show. Taraba, the highest, cannot be told apart from Abia, the second highest. Of 73 comparisons the state chart checks, 20 hold up.

I expected neighbouring states to look alike. They don't, at least not detectably: a spatial test (Moran's I) found no pattern that survives correction. With 37 states the test has little power, so this is not proof that there is no pattern.

## Disability and poverty

Using the NBS Multidimensional Poverty Index survey of 2021, and an analysis plan I registered publicly on OSF before splitting any poverty figure by disability, people in households with a member who has a severe difficulty are **11.7 percentage points more likely to be multidimensionally poor** than people in comparable households (95% confidence interval 6.1 to 17.2). That is an adjusted association, not proof that disability causes poverty: a strong enough factor I did not measure could explain it, and the site says how strong it would need to be.

## Limits

- The surveys count people living in households. People in institutions, and people without a household, are not in them.
- The questions are asked in the household questionnaire, so one person often answers for everyone: in the NBS survey, the household head or another adult who knows the household. Someone answering for another person may not know of every difficulty.
- Different surveys use different questions. The NBS poverty survey has its own disability questions, not the Washington Group's, so its figures are reported under its own definition.
- The site has automated accessibility tests and was checked by keyboard and with the NVDA screen reader, but it has **not yet been tested by a regular screen-reader user**. If you are one, please tell me what works and what doesn't; every page has a "report a problem" link that needs no account.

## The charts that check their own words

Every chart on the site comes with a description written from its data. A program checks every number and every comparison in that description against the data and its confidence intervals before the site is built. If a description says "Taraba is higher than Abia", the build fails, because the survey cannot show it. That checker is a Python library anyone can use: `pip install disability-access-charts`.

## Read more

- The site: https://batestguy.github.io/curb-cut/ (a [walkthrough video](https://batestguy.github.io/curb-cut/walkthrough.html) with captions)
- How the figures were made: the [methodology page](https://batestguy.github.io/curb-cut/methodology.html)
- The poverty analysis and its pre-registration: the [results page](https://batestguy.github.io/curb-cut/poverty.html) and https://osf.io/kes3p/
- The code, and every source checked and dated: https://github.com/batestguy/curb-cut

*Sources: The DHS Program, Nigeria Demographic and Health Survey 2024 (National Population Commission and ICF); National Bureau of Statistics, Multidimensional Poverty Index Survey 2021; JONAPWD, 2025 Assumptive Disability Disaggregated Data. Estimates by Curb Cut from the microdata, used under each survey's terms; only disclosure-checked aggregates are published.*
