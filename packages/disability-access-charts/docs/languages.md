# Languages: Hausa, Yoruba, Igbo and Nigerian Pidgin (0.4)

**Status: drafted by an AI model (Claude, 2026-11-06), not reviewed by a native speaker.** The author decided on 2026-11-04 that P6 would have no outside reviewers. Anything that shows these texts should say they are AI-drafted and unreviewed. `alt_text_translations` marks every text `reviewed: false`.

| Code | Language | Spelling used |
|---|---|---|
| `ha` | Hausa | Boko, with the hooked letters ɓ ɗ ƙ ƴ and ʼ (U+02BC) for the glottal stop; no tone or length marks, as in everyday print |
| `yo` | Yorùbá | standard orthography with tone marks and dots below (ẹ ọ ṣ); stacked marks such as ọ̀ use a combining accent, since they have no single code point |
| `ig` | Igbo | standard spelling with ị ọ ụ ṅ; tone marks left out, as in most printed Igbo |
| `pcm` | Naijá (Nigerian Pidgin) | the everyday spelling of BBC News Pidgin ("di", "dey", "wey", "pass"), no tone marks |

## What is translated, and what is not

Each table (`_lang/<code>.py`) has exactly English's keys and placeholders (a test checks this):

- `TEMPLATES`: the description sentences;
- `FINDINGS`: the statistical findings' sentences and lines;
- `MAP_TEXT`: the choropleth's introduction, class labels and class sentence;
- the claim checker's vocabulary (superlatives, comparison verbs, hedges, negation and qualifier words, list joiners, rank patterns, number words, total and share wording).

Left in English on purpose, with the same keys: `MESSAGES` (the checker's problem reports, read by developers) and `MAP_LEGEND` (what a page announces when a legend button is pressed: the Curb Cut site's interface is English, so its announcements are too).

Numbers are always digits with "." as the decimal point and "," between thousands, as in English, so the claim checker reads them the same way. How BBC Hausa, Yoruba, Igbo and Pidgin write numbers has not been checked (`docs/verification.md` D28).

## Choices made in drafting

- **Plain words over literary ones.** For example Yoruba "ìfojúbù" (estimate), "ìwádìí" (survey), Igbo "atụmatụ" (estimate), "nnyocha" (survey), Hausa "ƙiyasi" (estimate), "bincike" (survey).
- **"The survey can / cannot show a difference"** is the sentence that matters most. Hausa uses "binciken ya iya / ya kasa nuna bambanci" (the survey was able / unable to show a difference), which avoids Hausa's split negation "ba ... ba" so the negative is one phrase. Yoruba "ìwádìí náà lè / kò lè fi ìyàtọ̀ hàn", Igbo "nnyocha ahụ nwere ike / enweghị ike igosi ọdịiche", Pidgin "di survey fit / no fit show difference".
- **Hedges come before the superlative** in Hausa, Yoruba and Igbo ("Ƙiyasi mafi yawa", "Ìfojúbù tó ga jùlọ", "Atụmatụ kachasị elu": the estimate that is highest), as their grammar puts the noun first.
- **Counting nouns before their numbers** in Hausa, Yoruba and Igbo ("Ɗigo 37", "Àmì 37", "Ntụpọ 37"), in the singular for Hausa, as Hausa often does after numerals ("mutum biyar").
- **Ranks with digits** ("ƙiyasi na 2 daga sama", the 2nd estimate from the top), so a rank never needs a long spelled ordinal (Yoruba's go far past 10 by subtraction). Pidgin keeps English ordinals ("di second highest estimate").
- **Genderless Hausa where the noun is unknown**: "duk" (every, all) and "duka" (all of them) rather than "kowane / kowace", because a template cannot know a category label's gender. Where a template names its own noun, the noun's gender is used as best known; this is the most likely place for errors.
- **Names are not translated by the library.** The caller passes translated category labels, interval labels, titles, sources and any names (`Translation.names`); names not given stay as they are, as Nigeria's state names do.

## Disability terms and the NCPWD simplified Act (D26)

The National Commission for Persons with Disabilities and The Leprosy Mission Nigeria published a simplified Disability Act in Hausa, Yoruba and Igbo (`docs/verification.md` D26). **Its terms could not be confirmed**: the report of it could not be fetched on 2026-11-06 (HTTP 403), and no copy of the simplified Act was found. The library's tables contain no disability terms at all (only the caller's titles do). The Curb Cut site's glossary (`packages/transform/translations.yml`) uses the widely printed terms Hausa "nakasa", Yoruba "akanda ẹ̀dá", Igbo "nkwarụ" and Pidgin "disability"; they should be compared with the simplified Act when a copy is found.

## Screen readers

None of the four languages is in eSpeak NG's language list, so NVDA has no built-in voice for them (D27). These descriptions serve **readers, not listeners**. What NVDA does with text marked `lang="yo"` (and the others) still has to be tested by hand.

## The claim checker

How each language's vocabulary is read, and which checks are English and Pidgin only, is in [the claim checker reference](claim-checker.md#other-languages-04). In short: Yoruba and Igbo are read without combining marks (folding); hedges may come before the superlative; comparisons may be verbs; counting nouns may come before their numbers; and ratio words are recognised only in English and Pidgin. The vocabularies are small and cover the generated wording; hand-written text in these languages is checked much less thoroughly than English.

## Changing a translation

A reviewer who improves a text edits it in the document's `alt_text_translations` (or, better, in the table, so every chart gets it) and sets `origin` to `"human"` and, once a native speaker has checked it, `reviewed` to `true`. The audit still runs that language's claim checker and requires the English description's numbers; only the "matches the template" check is skipped for `"human"` texts.

## Samples (synthetic data; the test suite's `dot_doc()`)

- **Hausa:** "Ƙiyasi mafi yawa: Kano, 20.0%, kuma binciken ya iya nuna bambanci da ƙiyasi na gaba, Lagos, 15.0%."
- **Yoruba:** "Ìfojúbù tó ga jùlọ: Kano, 20.0%, àti pé ìwádìí náà lè fi ìyàtọ̀ hàn pẹ̀lú ìfojúbù tó kàn, Lagos, 15.0%."
- **Igbo:** "Atụmatụ kachasị elu: Kano, 20.0%, ma nnyocha ahụ nwere ike igosi ọdịiche ya na atụmatụ na-esote, Lagos, 15.0%."
- **Pidgin:** "Di highest estimate: Kano, 20.0%, and di survey fit show difference from di next estimate, Lagos, 15.0%."
