# Statistical findings: method and limits

`findings=True` on `bar()`, `grouped_bar()` or `dot()` (or `statistical_findings(data)` directly) adds a `findings` block to a chart document. It answers one question: **which differences between these survey estimates are larger than their uncertainty allows, once we allow for how many differences we looked at?**

It is **descriptive multiple-comparison control**. It describes estimates. It does not explain them, it is not a causal analysis, and "not supported" does not mean "the same": a survey cannot show that two groups are equal.

## The families, declared before the data

The comparisons come from the structure of the chart, not from looking at which differences are large. Four families are fixed in the code (`findings.FAMILIES`), and every comparison in them is counted, whether or not it is supported:

| Family | What is compared | How many (one series of *n* categories) |
|---|---|---|
| `extremes` | The highest estimate against the next one, and the lowest against the next one. Ties are compared as a group. | 2 (more with ties) |
| `gaps` | Two series in the same category, e.g. women against men in one state, for every pair of series and every category. | 0 with one series; *n* per pair of series |
| `rankings` | Every other pair of neighbours in the ranking (highest first, ties in chart order). Pairs already in `extremes` are not counted twice. | *n* − 3 |
| `outliers` | Each estimate against an overall value given as a `Reference`, e.g. the national estimate. Empty without a reference. | *n* |

On Curb Cut's state dot plot (37 states, one series, the national estimate as the reference) that is 2 + 34 + 37 = **73 comparisons**.

## The test

It is the claim checker's interval test (`describe.difference_test`), written as a p-value:

- Each standard error comes from the interval: the **larger** half-width divided by the normal quantile of the interval's level (1.96 for a 95% interval). An asymmetric interval therefore gives a conservative standard error. A chart with standard errors rather than intervals passes `lower = value − 1.96·se` and `upper = value + 1.96·se`.
- The difference *d* between two estimates has standard error *s* = √(se_a² + se_b²), and the two-sided p-value is *p* = 2(1 − Φ(|*d*| / *s*)).
- The checker's test, |*d*| > 1.96 *s*, is exactly *p* < 0.05. So a supported finding also passes the claim checker.

## The correction: Benjamini-Hochberg at q = 0.05

All the comparisons that were tested (every family and every series together) form **one** family for the false discovery rate. Benjamini-Hochberg (1995) adjusts the p-values: sorted ascending, *p*_adj(*i*) = min over *j* ≥ *i* of (*m* / *j*) · *p*(*j*), capped at 1. A comparison is **supported** when *p*_adj ≤ *q* (and, as a guard, the checker's own test passes). The default is *q* = 0.05 (`fdr_q=` changes it): among the supported findings, at most about 5% are expected to be false discoveries, on average.

Why BH and not Bonferroni: with 73 comparisons, Bonferroni controls the chance of even one false finding and would hide most real differences between states. BH controls the expected *share* of false findings among those reported, which is what a reader of a list of findings cares about. BH is proven for independent or positively dependent tests (Benjamini and Yekutieli, 2001). Comparisons that share a state or the reference are dependent, and we have not shown the positive-dependence condition holds for every pair, so treat the 5% as a nominal rate.

## Precision and missing cells

A series may carry a precision flag per estimate (`Series(..., precision=...)`): `reliable`, `review`, `unreliable` or `suppressed`. Curb Cut uses the NCHS standard plus a 10-event rule.

- **review**: the comparison is tested and counted. A finding that involves it is **hedged**: its sentence is followed by "Read with care: Kano's estimate is flagged for review."
- **unreliable** or **suppressed**: the comparison is **not tested**. It goes to `dropped_comparisons`, is counted in `dropped`, and is not part of the BH family. The block says "N more comparisons not tested, because they involve an estimate that is suppressed or too imprecise."
- **Left out of the chart** (no data, or suppressed for disclosure, so there is no value to plot): pass the names as `withheld=`. They are not compared, and the block names them: "Not shown or compared (1): Zamfara; too few respondents or no data." Never put a suppressed value in a chart just to flag it.

The families are built from every plotted estimate, flagged or not, so a flagged estimate at an extreme drops that extreme's comparison rather than moving the comparison to the next estimate.

## What the block holds

| Key | What it holds |
|---|---|
| `method` | the test, z = 1.96, how the standard errors are taken, `benjamini-hochberg`, `q`, the families, the language |
| `checked`, `supported`, `dropped` | the counts |
| `families` | the same counts per family |
| `comparisons` | every tested comparison: its family, both cells (series, category, value, interval, flag), the difference, the threshold 1.96·*s*, *p*, *p*_adj, `supported`, `hedged` |
| `dropped_comparisons` | every comparison not tested, and why |
| `statements` | the supported findings as sentences, each with the comparisons it rests on |
| `lines` | `count` ("73 comparisons checked, 20 supported."), `method`, and `none`, `dropped`, `withheld` when they apply |
| `reference`, `withheld`, `caveats` | the overall value, the left-out categories, and the caveats that apply |

The sentences are built from templates (`_lang/en.py`, `FINDINGS`):

- extremes: "Highest estimate: Taraba, 11.3%, and the survey can show a difference from the next estimate, Abia, 10.6%." (only when every comparison in the group is supported);
- rankings: "Abia, 10.6%, is higher than Benue, 6.4%.";
- gaps: "Kano: Women, 6.0%, is higher than Men, 3.0%.";
- outliers, one sentence per series and direction: "Taraba, 11.3%, Abia, 10.6%, and Kano, 4.6%, are each higher than Nigeria as a whole, 3.0%."

A name that is also a word of these sentences ("Care", "Review") is refused, since the checker could not tell it from the word.

The data-built alt-text is unchanged by findings: it still says, per extreme, whether the survey can show a difference from the next estimate **without** a multiple-comparison correction (as in 0.1). So the alt-text can say "can show a difference" where the findings, after correction, do not list that difference. The findings are the stricter of the two.

## What the audit checks

`audit()` (and so `disability-access-charts check`) runs these checks on any document with a `findings` block. They carry `wcag: "n/a"`: they check the statistics, not accessibility.

| Check | Fails when |
|---|---|
| `findings-counts` | `checked`, `supported` or `dropped` disagree with the lists, the families do not add up, or the count, method or left-out lines do not state the counts |
| `findings-cite-data` | a comparison names a series or category that is not in the `data` block (or the reference), its numbers or flag differ from the data, or a sentence cites a comparison that is not listed or not supported |
| `findings-match-data` | recomputing the block from the `data` block gives different comparisons, p-values, BH results, sentences or caveats |
| `findings-hedged` | a tested comparison involves an unreliable or suppressed estimate, or a finding that involves a `review` estimate has no "flagged for review" sentence |
| `findings-claims` | the claim checker finds an error in a sentence (outlier sentences are checked with the reference added as one more category) |

`findings-unchecked-claims` is a warning for anything the checker could not test. The checker's independence warning is expected for gaps between series (and for parts of one whole) and is covered by the block's `independence` caveat, so it is not repeated there.

## Limits

- **Independence.** The test treats the two estimates as independent. Two series in the same category (women and men in one state) come from the same survey clusters, so a gap test is approximate. An estimate compared with an overall value that contains it is positively correlated with it; ignoring that makes the test **conservative** (it finds fewer differences than a test that used the covariance).
- **Normal intervals.** The standard errors come from the intervals, assuming they are roughly normal. Korn-Graubard or logit intervals for small proportions are asymmetric; the larger half-width keeps the test conservative but not exact.
- **The family is the block.** The false discovery rate is controlled within one chart's block. Findings across several charts on a page are not corrected together.
- **"Supported" is not "large".** A supported difference can be small in practical terms; a difference that is not supported can still be real.
- **Not causal.** None of this says why estimates differ.

## References

Benjamini, Y. and Hochberg, Y. (1995). Controlling the false discovery rate: a practical and powerful approach to multiple testing. *Journal of the Royal Statistical Society, Series B*, 57(1), 289–300.

Benjamini, Y. and Yekutieli, D. (2001). The control of the false discovery rate in multiple testing under dependency. *Annals of Statistics*, 29(4), 1165–1188.
