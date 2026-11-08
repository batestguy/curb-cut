# Paper handoff

Written 2026-11-08, after the P7 gate (all phases complete, release 1.0.0). Papers are **outside the plan** and optional: nothing here is scheduled until the author decides. This page records where to submit and what each paper still needs. The gap analysis, reporting checklists and reviewer objections are in [`publication-readiness.md`](publication-readiness.md) (2026-11-04); read that next.

## The three papers

| # | Paper | Strength | Status |
|---|---|---|---|
| 1 | **Disability in the household and multidimensional poverty in Nigeria** (NBS MPI 2021; pre-registered on OSF, https://osf.io/kes3p/; DoubleML adjusted association) | The strongest science: pre-registered, results public, robustness done | Results and brief exist (`docs/brief/`, the poverty page); no manuscript |
| 2 | **State disability prevalence from Nigeria DHS 2024** (Washington Group Short Set), with disclosure-checked open aggregates, precision flags and the reproduced report tables | Solid, policy-relevant; the NDHS report already publishes state figures by sex (D46), so novelty is both sexes with intervals, open data and method | Results public; no manuscript |
| 3 | **`disability-access-charts`**: chart descriptions checked against the data and its confidence intervals | Novel tool; peer review of the software itself | Library on PyPI (0.4.0), DOI for the project; no `paper.md` |

## Where to submit

### Verified (2026-11-08)

Scopus status from SCImago (which ranks only Scopus-indexed sources; data "as of March 2026"), read in the author's browser. Fees from the official DOAJ journal list (`https://doaj.org/csv`, downloaded the same day).

| Journal | Country | Scopus (SCImago) | Fee (DOAJ) | Fits | Note |
|---|---|---|---|---|---|
| **African Journal of Disability** (AOSIS) | South Africa | ✅ coverage 2015, 2018–2026; **Q2**; SJR 2025 0.534; H-index 26; Rehabilitation; Physical Therapy, Sports Therapy and Rehabilitation | ZAR 18,975; **waiver policy: yes** | Paper 1 (first choice) or 2 | Best topic fit and rank. Ask AOSIS about the waiver before submitting; its terms were not found. |
| **Disability, CBR and Inclusive Development** | DOAJ: Ethiopia; SCImago: Netherlands (Vrije University) | ✅ coverage 2011–2025; SJR 2025 0.213 | **None** | Paper 2 (first choice) or 1 | Free and Scopus-indexed; focus on low- and middle-income countries; lower rank. |
| **Journal of Open Source Software (JOSS)** | International | ❌ a February 2024 report says Scopus refused to index it | **None** | Paper 3 | Fastest route (open review on GitHub); a short `paper.md`; Crossref DOI. Not a Scopus line. |

### Candidates not yet checked in Scopus

SCImago began showing a "Verify you are human" checkbox, which an automated session must not tick, so these stopped here. Fees are from DOAJ. Check each on SCImago (search by ISSN) before relying on it.

| Journal | Country | Fee (DOAJ) | eISSN | Fits |
|---|---|---|---|---|
| Southern African Journal of Public Health | South Africa | None | 2708-9509 | 1 or 2 |
| Ethiopian Journal of Health Sciences | Ethiopia | None | 2413-7170 | 2 |
| South African Journal of Science | South Africa | None | 1996-7489 | 1 or 2 (broad) |
| Malawi Medical Journal | Malawi | None | 1995-7270 | 2 |
| African Population Studies | South Africa | US$250, waiver | 2308-7854 | 2 (demography) |
| South African Journal of Occupational Therapy | South Africa | None | 2310-3833 | disability-adjacent |
| Rehabilitation Advances in Developing Health Systems | South Africa | ZAR 17,802, waiver | 3005-9437 | 1 or 2 |
| South African Computer Journal | South Africa | ZAR 6,000, waiver | 2313-7835 | 3 |
| The African Journal of Information and Communication | South Africa | None | 2077-7213 | 3 (weaker fit) |
| The Egyptian Statistical Journal | Egypt | None | 2786-0086 | methods note |

### Outside Africa (from `publication-readiness.md` and 2026-11-08 searches)

- **Disability and Health Journal** (Elsevier): the earlier first choice for papers 1 and 2. Large hybrid journals are usually free on the standard (non-open-access) route; confirm the current options when submitting. Q1 status not confirmed.
- **Journal of Statistical Software**: no author fees, listed as Scopus-indexed; long papers and slow review (often a year or more). A possible second home for paper 3.
- **SoftwareX** (about US$760 by secondary sources) and **Journal of Open Research Software** (about £400; sources disagree): Scopus-listed, but not free.

### Corrections to earlier advice

- The **Ghana Medical Journal charges US$300** (DOAJ, with a waiver), not "no fees" as a secondary compilation said.
- The Nigerian journals mentioned in conversation (Nigerian Journal of Clinical Practice, Annals of African Medicine) are not in DOAJ; check their fees on their own sites. The Journal of the Nigerian Society of Physical Sciences charges ₦25,000–40,000 or more (its own APC page; Scopus status only from an aggregator).
- Aggregator sites that list "free Scopus journals in Nigeria" disagree with one another and with DOAJ; do not rely on them.

## Recommendation

1. **Paper 1 → African Journal of Disability**, with a waiver request. The pre-registration, the results and the robustness checks already exist; what remains is the manuscript.
2. **Paper 2 → Disability, CBR and Inclusive Development** (free, Scopus).
3. **Paper 3 → JOSS** when an API reference exists and the claim checker's accuracy has been measured. JOSS is not in Scopus.

Peer review takes months for 1 and 2 (typically 3–12). None of these is quick.

## What each paper still needs

**All:**
- An author statement on AI assistance (code and drafts were AI-assisted; the pre-registration already discloses it, `docs/preregistration.md`).
- Funding (none) and competing-interest statements.
- **Survey terms:** send a PDF of every publication to the DHS Program (references@dhsprogram.com) and an electronic copy of every publication using MPI data to the NBS National Data Archive. Use the data only for the registered project, "Curb Cut: disability prevalence and poverty in Nigeria".
- Cite the code by its DOI: https://doi.org/10.5281/zenodo.24050358 (version 1.0.0: 10.5281/zenodo.24051559).

**Paper 1:** the STROBE (cross-sectional) checklist and pre-registration transparency items in `publication-readiness.md` §2.1–2.2; report every pre-registered estimate, including the secondary and exploratory GHS result, and the deviations file (`docs/preregistration-deviations.md`); keep the "adjusted association, not a causal effect" wording (`poverty_text.forbidden`).

**Paper 2:** STROBE plus the survey-design items (§2.3); state plainly what the NDHS report already publishes (D46) and what is new.

**Paper 3:**
- `paper.md` (summary, statement of need, comparison with maidr, Olli and a11yviz; the library README's "How it compares" is the base).
- An **API reference** (generated from the docstrings; the MkDocs site was dropped because Material for MkDocs reached end of life, so use Sphinx or a simpler generator).
- A **claim-checker accuracy measurement**: false claims passed and true claims rejected on a corpus of real chart descriptions (§3.2.2).
- Ideally a user evaluation with screen-reader users (§3.2.1); without it, say so as a limitation.
- A Zenodo archive of the library release that the paper describes.

## How the journal facts were checked

- Scopus's own source list needs a Scopus login, so SCImago was used. Being listed in SCImago means the journal was in Scopus for the years shown; check the current year before submitting.
- SCImago blocks scripted access (Cloudflare); its pages were read in the author's Chrome. It later asked for a human check, which the session did not complete.
- DOAJ's CSV gives each journal's publisher country, fee, amount and waiver policy. Fees change: confirm on the journal's site at submission.

## Sources

- DOAJ journal list: https://doaj.org/csv (2026-11-08)
- SCImago, African Journal of Disability: https://www.scimagojr.com/journalsearch.php?q=21100853560&tip=sid&clean=0
- SCImago, Disability, CBR and Inclusive Development: https://www.scimagojr.com/journalsearch.php?q=21101276702&tip=sid&clean=0
- JOSS: https://joss.theoj.org/ ; DOAJ entry (no fees): https://doaj.org/toc/2475-9066 ; Scopus refusal reported in the International Science Council's open-science round-up, January 2024: https://tagteam.harvard.edu/hub_feeds/119/feed_items/9840047
- Journal of Statistical Software: https://en.wikipedia.org/wiki/Journal_of_Statistical_Software ; https://www.editage.com/research-solutions/journal/journal-of-statistical-software/9689
- SoftwareX on DOAJ: https://doaj.org/toc/aebea1c2d72c41cfae9da55edb18f140
- Journal of Open Research Software: https://www.editage.com/research-solutions/journal/journal-of-open-research-software/27065
- JNSPS fees: https://journal.nsps.org.ng/index.php/jnsps/about/apc
- Scopus source list (login required): https://www.elsevier.support/scopus/answer/what-is-the-scopus-source-list
