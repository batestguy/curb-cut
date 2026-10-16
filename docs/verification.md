# P0 verification log

Every check that the design depends on, with its source and the date it was checked. A check is done only when **Result**, **Source** and **Checked** are filled in. Planning-stage findings (2026-10-16) are in `PLAN.md`; this file records the P0 confirmations.

Status key: ☐ open · ☑ confirmed · ✗ contradicts the plan (stop and revisit `PLAN.md`)

## Accounts

| # | Item | Status | Notes | Checked |
|---|---|---|---|---|
| A1 | PyPI account created, 2FA on | ☐ | | |
| A2 | `disability-access-charts` claimed on PyPI by publishing 0.0.1 from CI via trusted publishing (`a11y-viz` was blocked as too similar to the existing `a11yviz`) | ☐ | | |
| A3 | NBS microdata portal registration | ☐ | | |
| A4 | World Bank Microdata Library registration | ☐ | | |
| A5 | DHS Program registration (optional; paused as of 2026-10-16) | ☐ | | |

## Data and licensing

| # | Question | Status | Result | Source | Checked |
|---|---|---|---|---|---|
| D1 | Is NBS MPI 2021 representative at state level? (sampling documentation) | ☐ | | | |
| D2 | Do GHS-Panel W3/W4 disability questions match W5's (Washington Group)? | ☐ | | | |
| D3 | NBS republication terms: may weighted aggregates be published? | ☐ | | | |
| D4 | NBS written confirmation that aggregates may be published (email sent / reply) | ☐ | | | |
| D5 | World Bank Microdata Library terms for GHS-Panel aggregates | ☐ | | | |
| D6 | JONAPWD Assumptive Data 2025 PDF downloaded; licence notice | ☐ | | | |
| D7 | JONAPWD PDF confirmed scanned (no text layer) → OCR needed | ☐ | | | |
| D8 | NBS Demographic Bulletin 2023 has state projections usable as denominators | ☐ | | | |
| D9 | WorldPop licence (CC BY 4.0) and the product used | ☐ | | | |
| D10 | geoBoundaries Nigeria ADM1 licence | ☐ | | | |

## LLM quotas (record what the console actually shows)

| # | Item | Status | Result | Source | Checked |
|---|---|---|---|---|---|
| L1 | Gemini Flash free tier: RPM / RPD / TPM for the model used | ☐ | | | |
| L2 | Gemini free tier: are prompts used for training? | ☐ | | | |
| L3 | Groq free tier: RPM / RPD / TPM for the model used | ☐ | | | |

## WCAG 2.2 criteria wording (quote the normative text)

| # | Criterion | Status | Wording | Source | Checked |
|---|---|---|---|---|---|
| W1 | 1.1.1 Non-text Content | ☐ | | | |
| W2 | 1.4.3 Contrast (Minimum) | ☐ | | | |
| W3 | 1.4.11 Non-text Contrast | ☐ | | | |
| W4 | 2.1.1 Keyboard | ☐ | | | |

## Repo bootstrap

| # | Item | Status | Checked |
|---|---|---|---|
| R1 | uv workspace, ruff, pyright, pytest pass locally (Python 3.12.13) | ☑ | 2026-10-16 |
| R2 | renv 1.3.0 initialised (R 4.5.2, explicit snapshots); `renv.lock` to be committed | ☑ | 2026-10-16 |
| R3 | pre-commit installed; restricted-zone guard blocks a staged `data/restricted/` file | ☑ | 2026-10-16 |
| R4 | GitHub repo `curb-cut` created; CI green on `main` | ☐ | |

## P0 gate

- [ ] CI green
- [ ] Every row above confirmed or marked ✗ with a decision recorded in `PLAN.md`
- [ ] Author review
