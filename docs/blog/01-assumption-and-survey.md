# Nigeria's disability numbers are an assumption. Here is what the surveys measured.

*Draft for the author's edit, 2026-11-08. Every number is from the live site's published data or `docs/verification.md`; check them again after any edit.*

You will often hear that about 35 million Nigerians are disabled. That figure, from JONAPWD's 2025 *Assumptive Disability Disaggregated Data*, is the projected 2025 population (232,676,020) multiplied by a global benchmark of 15% (pp. 5 and 7). Nobody was counted.

I am a statistician in Bauchi and a wheelchair user. Nigeria does have measurements; they had not been put in one place, with their uncertainty, in a form a screen-reader user can read. So I built [Curb Cut](https://batestguy.github.io/curb-cut/).

## Data and method

- **Data:** the Nigeria DHS 2024, which asked every household member aged 5 and over the Washington Group Short Set: six questions on difficulty seeing, hearing, walking, remembering, self-care and communicating.
- **Privacy:** the microdata stay on my computer. Only survey-weighted estimates that pass a disclosure check (no cell under 30 respondents) are published.
- **Checks:** my code first reproduces 1,360 cells of the official NDHS report. Every estimate has a 95% confidence interval, and state comparisons are corrected for multiple testing.

## What the survey measured

**3.0% of adults aged 18 and over (95% CI 2.8% to 3.2%) have a lot of difficulty with, or cannot do, at least one of the six activities.** The official report's broader count, *any* difficulty among people aged 15 and over, is 15.5%.

The two count different things: serious difficulty, or any difficulty at all. The 15% behind the 35 million is neither: it is a global benchmark applied to a projection.

States differ: estimates range from 0.8% in Lagos to 11.3% in Taraba. After correction, 7 states are clearly above the national figure and 12 clearly below. Many differences are too small to show: of 73 comparisons, 20 hold up, and Taraba cannot be told apart from Abia, the second highest. Neighbouring states show no detectable pattern, though with 37 states the test has little power.

## Disability and poverty

In a pre-registered analysis of the NBS poverty survey (2021), people in households with a member who has a severe difficulty are **11.7 percentage points (95% CI 6.1 to 17.2) more likely to be multidimensionally poor** than people in comparable households. This is an association, not proof of cause.

## Limits

- The surveys cover people in households, not in institutions.
- One person often answers for the whole household, and may not know every difficulty.
- The site passed automated, keyboard and NVDA checks, but has **not yet been tested by a regular screen-reader user**. If you are one, please use the "report a problem" link on any page.

## Charts that check their own words

Every chart's description is written from its data, and a program checks each number and comparison against the confidence intervals before the site is built. "Taraba is higher than Abia" would fail. The checker is open source: `pip install disability-access-charts`.

**Read more:** [the site](https://batestguy.github.io/curb-cut/) · [walkthrough video](https://batestguy.github.io/curb-cut/walkthrough.html) · [methodology](https://batestguy.github.io/curb-cut/methodology.html) · [poverty results](https://batestguy.github.io/curb-cut/poverty.html) and [pre-registration](https://osf.io/kes3p/) · [code and sources](https://github.com/batestguy/curb-cut)

*Sources: Nigeria DHS 2024 (NPC and ICF); NBS Multidimensional Poverty Index Survey 2021; JONAPWD (2025). Estimates by Curb Cut from the microdata under each survey's terms; only disclosure-checked aggregates are published.*
