# The claim checker: full rules

This page is the complete reference for `check_alt_text` in `disability-access-charts` 0.3; the rules have not changed since 0.2. The [README](../README.md) has the short version. The same rules are in the module docstring of `disability_access_charts/describe.py`.

**Terms.** A *description* is any text about a chart: its alt-text (the text alternative of WCAG 2.2 SC 1.1.1; W3C, 2023), a caption or an LLM's rewording. A *claim* is a statement in it that the checker recognises and can test against the chart's data: a number attributed to a category, an extreme, a pairwise comparison, a ratio, a rank or an equality. A *category* is one labelled position on the chart (a bar, a dot row, a map region); a *series* is one set of values across the categories. An *error* means the checker found a claim false; a *warning* means it found wording it could not test, or a result to read with care.

**What a pass means.** No errors means that **no recognised claim was found false**. Wording the checker does not recognise is warned about where it detects it, and otherwise not checked. A pass does not make a description true, complete or good.

**Numbers.** A number belongs to the name just before it when only a verb or "of / at / :" separates them ("Lagos's rate is 8.0%"), to the name after it in "2.0% in Ibadan", and otherwise to the nearest category named in its part of the clause, so "Kano, 11.9%" fails if 11.9% is Lagos's figure. In a "respectively" clause the names and numbers pair in order. "X to Y" next to a name with an interval must be its lower and upper bound, in that order. A number in a clause that names no category is an error if it is in nobody's data and a warning if it is. It must be one of that category's figures (value, interval bound or share of the total); the checker does not verify which of those roles the sentence gives it. A number followed by "% of the total" must be the share. Chart-wide numbers count only with the words that announce them: the number of categories before a counting noun ("37 bars", "4 states", "the four states", where a wrong count is an error), the total after "Total:" or before "in total". Rounding to the written decimals is allowed. Numbers in the title, source and interval label are skipped.

**Claims checked** (English; for the other languages see "Other languages" below):

- extremes: *largest, highest, smallest, lowest, the most, the fewest*;
- pairwise: "A *higher / lower / more / fewer / larger / smaller / less* than B" and "A *trails / lags* B", with lists of names joined by commas, "and" or "or" on either side checked pair by pair. A second comparison that starts with its comparator ("and higher than", "but it is higher than") is about the first subject; one with a new unnamed subject ("but the national rate is higher") is warned about, not checked;
- ratios: *twice*, *half*, *double*, *triple*, *N times*, within 5% of the actual ratio;
- ranks: "ranked N of M", "3rd", "the second-highest", "number one", "#2" (ties share a rank);
- equality: "A is *the same as* B";
- "the survey *can / cannot* show a difference from B", checked both ways;
- "no difference", "not different" and similar always fail.

**With confidence intervals** the checker tests the claim rather than reading the point estimates:

- "A is higher than B" passes only if |a − b| > 1.96 · √(se_a² + se_b²) (a two-sided z-test of the difference at the 5% level), with each se = the interval's half-width ÷ 1.96 (or the normal quantile for the level in the interval label, such as "90% CI"). For an asymmetric interval it uses the **larger** half-width, which is conservative. A zero-width interval (such as 0 events, interval 0 to 0) has no standard error to test with, so the claim never passes: the suggestion is "the survey cannot show a difference".
- **Assumptions:** roughly symmetric, normal intervals, **independent groups**, and **no correction for multiple comparisons**. When groups may not be independent (two series for the same category, or categories that are parts of one whole) the result comes with a warning.
- "A is the highest" fails unless A is separated from **every** other group; "A has the highest estimate" is the accepted hedged form.
- Ratios are checked on the point estimates and also need a supported difference. Ranks are checked on the point estimates, with a warning when a neighbour in the ranking cannot be separated.
- "The same as" always fails: a survey can't show that two groups are equal. The suggested wording is "the survey cannot show a difference".

**Warned about, not checked:** negated claims ("not higher", "isn't the highest"), qualified ones ("one of the highest", "the joint highest", "more than twice"), contrasts ("rather than", "unlike"), words on the unchecked list (*greater, exceeds, outnumbers, beats, similar, comparable, increased, doubled, significantly*, "as high as", "up to", …), unknown "-er than" and "the -est" forms, numbers written as words (other than a count before the label), a name excluded after a comparison ("higher than Lagos but not Abuja"), and a clause that names two or more groups without a recognised claim, unless it is a plain list of values in which every named group has its own number.

**Not understood at all:** causes, trends over time, comparisons with a stated number ("more than 5 million"), differences written as numbers ("3 points higher"), claims about the total, and wording the checker does not detect.

**Unsafe names.** Category and series names that are also checker words ("Highest", "Total", "Twice", "Not", "Second", "the same", …) are refused with a clear error, because the checker could not tell the name from the word. Rename them, for example "Highest group".

Generated alt-text uses the hedged wording ("highest estimate"), gives each interval with its label, says whether the survey can show a difference from the next estimate, and puts the summary before the detail, following a short-paper interview study with screen-reader users (Sharif et al., 2023). The tests hold every generated text to its own checker.

## Other languages (0.4)

Hausa (`ha`), Yoruba (`yo`), Igbo (`ig`) and Nigerian Pidgin (`pcm`) each have their own vocabulary (`_lang/<code>.py`), read by the same checker. The tables were drafted by an AI model and have not been reviewed by a native speaker. The checker learned five things for them, all off in English, so English results are unchanged:

- **Folding** (`FOLD`, Yoruba and Igbo): the text, names and vocabulary are read without combining marks (tone marks, dots below), because a letter such as "ọ̀" has no single code point and Python's `\b` treats a combining mark as a non-word character. Problem messages then quote the clause without its marks.
- **The hedge before the superlative** (`HEDGE_BEFORE`): "Ƙiyasi mafi yawa", "Ìfojúbù tó ga jùlọ", "Atụmatụ kachasị elu" (the estimate that is highest) count as hedged, like English's "highest estimate".
- **Comparatives as verbs** (`UP_VERBS`, `DOWN_VERBS`): Hausa "ya fi / ya gaza", Yoruba "ga ju / kéré ju ... lọ", Igbo "dị elu / dị ala karịa". Pidgin keeps English's form, with "pass" for "than" ("dey higher pass").
- **Counting nouns before their number** (`COUNT_BEFORE`; Hausa, Yoruba, Igbo: "Ɗigo 37", "Àmì 37", "Ntụpọ 37").
- **Ranks with digits**: "ƙiyasi na 2 daga sama", "ìfojúbù tó wà ní ipò 2 láti òkè", "atụmatụ nke 2 site n'elu" (2nd from the top). Pidgin uses English ordinals.

The interval level is read from a translated label too ("tazarar tabbaci ta 95%", `LEVEL`).

**Checked in every language:** numbers (attached to the nearest name, interval pairs, shares, totals, counts), extremes, comparisons, ranks, "can / cannot show a difference", "no difference" wording, equality wording, each language's negation and qualifier words, and the fallback warning for a clause that names two groups without a recognised claim.

**English and Pidgin only, and why that is safe here:** ratio words (Hausa "sau biyu", Yoruba "ìlọ́po méjì" and Igbo "okpukpu abụọ" put the multiplier before the number, which the ratio rule does not read), "but not Abuja" exclusions, and the warning for an unknown "the -est" superlative. These are forms a person might write by hand. The generated descriptions never contain them; a template translation must equal what the templates give (`alt-text-translation-matches-template`) and every translation must carry exactly the English description's numbers. A hand-edited translation (`origin: "human"`) using such wording would have those forms pass unchecked, which is one reason the audit also compares its numbers with the English description's.

The vocabularies are small: they cover the generated wording and common comparison words, not natural writing. The false-negative rate on hand-written text in these languages is unknown.

## The LLM gate

`polish_alt_text` keeps a model's rewording only if the checker reports **no errors and no warnings** in it, apart from the independence warning that the data-built text can carry too, and only if it keeps every category, every number, the interval label and the source of the data-built text. Otherwise the data-built text stays.

## Limits of the method

- **Coverage is a vocabulary.** The checker tests only the claim forms listed above, in English (and, from 0.4, the smaller AI-drafted vocabularies of Hausa, Yoruba, Igbo and Pidgin). Its false-negative rate (false claims it passes because it does not recognise them) has not been measured on a corpus of real descriptions; the test suite exercises the listed forms, not a sample of natural writing.
- **The interval test is approximate.** It assumes roughly normal, symmetric intervals and independent groups, uses the normal quantile rather than the survey design's degrees of freedom, and applies no multiple-comparison correction (see [the findings method](findings.md) for the corrected version used in findings blocks).
- **It checks truth, not usefulness.** Whether a description is clear, complete or helpful to a screen-reader user is outside what the checker can test.

## References

Sharif, A., Zhong, R. and Wang, Y. (2023). Conveying uncertainty in data visualizations to screen-reader users through non-visual means. In *Proceedings of the 25th International ACM SIGACCESS Conference on Computers and Accessibility (ASSETS '23)*. https://doi.org/10.1145/3597638.3614502

W3C (2023). *Web Content Accessibility Guidelines (WCAG) 2.2*. W3C Recommendation. https://www.w3.org/TR/WCAG22/
