# NDHS 2024 report tables (benchmark)

Figures cited from the Nigeria DHS 2023-24 final report (NPC and ICF, FR395), chapter 14,
transcribed by hand from the PDF on 2026-10-27: https://dhsprogram.com/pubs/pdf/FR395/FR395.pdf.
The report itself is not redistributed here.

- `fr395_table14_1.csv`: Table 14.1 (p. 443), household population 5+ (de facto), by domain
  and by age. Percentages; `number` is the weighted number of persons.
- `fr395_table14_2.csv`: Tables 14.2.1 (women, p. 444) and 14.2.2 (men, p. 446), de facto
  household members 15+, state rows. Domain columns are "some difficulty, a lot of difficulty
  or cannot do at all"; `some` / `a_lot` / `cannot` / `a_lot_or_cannot` are the highest level
  in at least one domain; `multi_domain` is "a lot of difficulty or cannot function at all in
  more than one domain"; `number` is weighted. Rows: all 37 states for both sexes; the six zones and urban/rural for both sexes (`zone: …`, `residence: …`); the wealth quintiles for men (`wealth: …`; the women's wealth rows are not transcribed); the men's total.

Used by `curbcut_ingest.validate_ndhs` (P4a step 0, `PLAN.md`) to check that our pipeline
reproduces the published tables. See `docs/verification.md` D46.
