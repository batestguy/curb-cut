# The claim checker: full rules

This page is the complete reference for `check_alt_text` in `disability-access-charts` 0.1. The [README](../README.md) has the short version. The same rules are in the module docstring of `disability_access_charts/describe.py`.

**What a pass means.** No errors means that **no recognised claim was found false**. Wording the checker does not recognise is warned about where it detects it, and otherwise not checked. A pass does not make a description true, complete or good.

**Numbers.** A number belongs to the name just before it when only a verb or "of / at / :" separates them ("Lagos's rate is 8.0%"), to the name after it in "2.0% in Ibadan", and otherwise to the nearest category named in its part of the clause, so "Kano, 11.9%" fails if 11.9% is Lagos's figure. In a "respectively" clause the names and numbers pair in order. "X to Y" next to a name with an interval must be its lower and upper bound, in that order. A number in a clause that names no category is an error if it is in nobody's data and a warning if it is. It must be one of that category's figures (value, interval bound or share of the total); the checker does not verify which of those roles the sentence gives it. A number followed by "% of the total" must be the share. Chart-wide numbers count only with the words that announce them: the number of categories before a counting noun ("37 bars", "4 states", "the four states", where a wrong count is an error), the total after "Total:" or before "in total". Rounding to the written decimals is allowed. Numbers in the title, source and interval label are skipped.

**Claims checked** (English):

- extremes: *largest, highest, smallest, lowest, the most, the fewest*;
- pairwise: "A *higher / lower / more / fewer / larger / smaller / less* than B" and "A *trails / lags* B", with lists of names joined by commas, "and" or "or" on either side checked pair by pair. A second comparison that starts with its comparator ("and higher than", "but it is higher than") is about the first subject; one with a new unnamed subject ("but the national rate is higher") is warned about, not checked;
- ratios: *twice*, *half*, *double*, *triple*, *N times*, within 5% of the actual ratio;
- ranks: "ranked N of M", "3rd", "the second-highest", "number one", "#2" (ties share a rank);
- equality: "A is *the same as* B";
- "the survey *can / cannot* show a difference from B", checked both ways;
- "no difference", "not different" and similar always fail.

**With confidence intervals** the checker tests the claim rather than reading the point estimates:

- "A is higher than B" passes only if |a − b| > 1.96 · √(se_a² + se_b²), with each se = the interval's half-width ÷ 1.96 (or the normal quantile for the level in the interval label, such as "90% CI"). For an asymmetric interval it uses the **larger** half-width, which is conservative.
- **Assumptions:** roughly symmetric, normal intervals, **independent groups**, and **no correction for multiple comparisons**. When groups may not be independent (two series for the same category, or categories that are parts of one whole) the result comes with a warning.
- "A is the highest" fails unless A is separated from **every** other group; "A has the highest estimate" is the accepted hedged form.
- Ratios are checked on the point estimates and also need a supported difference. Ranks are checked on the point estimates, with a warning when a neighbour in the ranking cannot be separated.
- "The same as" always fails: a survey can't show that two groups are equal. The suggested wording is "the survey cannot show a difference".

**Warned about, not checked:** negated claims ("not higher", "isn't the highest"), qualified ones ("one of the highest", "the joint highest", "more than twice"), contrasts ("rather than", "unlike"), words on the unchecked list (*greater, exceeds, outnumbers, beats, similar, comparable, increased, doubled, significantly*, "as high as", "up to", …), unknown "-er than" and "the -est" forms, numbers written as words (other than a count before the label), a name excluded after a comparison ("higher than Lagos but not Abuja"), and a clause that names two or more groups without a recognised claim, unless it is a plain list of values in which every named group has its own number.

**Not understood at all:** causes, trends over time, comparisons with a stated number ("more than 5 million"), differences written as numbers ("3 points higher"), claims about the total, and wording the checker does not detect.

**Unsafe names.** Category and series names that are also checker words ("Highest", "Total", "Twice", "Not", "Second", "the same", …) are refused with a clear error, because the checker could not tell the name from the word. Rename them, for example "Highest group".

Generated alt-text uses the hedged wording ("highest estimate"), gives each interval with its label, says whether the survey can show a difference from the next estimate, and puts the summary before the detail, following a preliminary interview study with screen-reader users (Sharif et al., ASSETS 2023). The tests hold every generated text to its own checker.

## The LLM gate

`polish_alt_text` keeps a model's rewording only if the checker reports **no errors and no warnings** in it, apart from the independence warning that the data-built text can carry too, and only if it keeps every category, every number, the interval label and the source of the data-built text. Otherwise the data-built text stays.
