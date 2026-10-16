# Status and handoff

The one page to read first. It says where things stand and what happens next. The rules live in `CLAUDE.md`, the roadmap in `PLAN.md`, and the P0 evidence in `docs/verification.md`. Update this page at every working session and every gate.

**Last updated:** 2026-10-16 · **Current phase:** P0 — accounts, checks, bootstrap

## Phases

| Phase | State | Gate |
|---|---|---|
| P0 Accounts, checks, bootstrap | 🟡 in progress | CI green ✅ · every check in `verification.md` confirmed or decided ⏳ · author review ⏳ |
| P1 Thin vertical slice | ⚪ not started | Live URL works by keyboard and with NVDA (author-tested) |
| P2 disability-access-charts 0.1 | ⚪ not started (0.0.1 contrast checks published) | Clean install reproduces examples; LLM mocked in tests |
| P3 Restricted zone + warehouse | ⚪ not started | `dbt build` green on fixtures; disclosure check passes |
| P4 Prevalence | ⚪ not started | Map and comparison live |
| P5 Poverty analysis | ⚪ not started | Pre-registration committed first; brief and results page live |
| P6 API + site polish | ⚪ not started | Accessibility 100 in CI; walkthrough video recorded |
| P7 Launch | ⚪ not started | — |

## Done so far (P0)

- Repo `batestguy/curb-cut` (public): uv workspace, renv, pre-commit restricted-data guard, CI green.
- PyPI name claimed: `disability-access-charts` 0.0.1 (WCAG contrast checks), published via trusted publishing. `a11y-viz` was blocked as too similar to the existing `a11yviz`.
- NBS and World Bank microdata accounts registered.
- **NBS MPI 2021 microdata obtained** (public-use request granted at once). Stored in git-ignored `data/restricted/nbs-mpi-2021/`, with a local hash manifest. The disability module (Section D) covers 213,820 people aged 5+. It includes:
  - the Washington Group Short Set: seeing `d2`, hearing `d3a`, walking `d5`, communicating `d9a`/`d10a`, self-care `d11a`, remembering `d12a`
  - extended items: upper body `d13a`/`d14a`, albinism `d15a`, affect `d16*`
  - assistive technology use `d22*`–`d26*`, including screen readers `d23h`

  Weights `hh_wgt` / `pop_wgt` / `indiv_wgt` are in Section A; senatorial district `a1b` and EA `a4` are there for the design.
- JONAPWD PDF downloaded (git-ignored). It **has a text layer**, so no OCR is needed.
- Research checks logged with sources in `verification.md`.

## Blocked / waiting

| Item | Waiting on | Since |
|---|---|---|
| NBS email on publishing aggregates (draft in Gmail) | **Author** to review and send; then NBS reply | 2026-10-16 |
| Gemini / Groq real quotas | Accounts (only needed at the alt-text step, P2) | 2026-10-16 |

## Next actions

1. **Claude:** GHS-Panel W3/W4/W5 questionnaires: do they ask the same disability questions (D2)? Then download GHS W5 (World Bank catalog 6410) with the author's approval.
2. **Claude:** check the Nigeria DHS 2024 access route (WB catalog 8029) as a second prevalence source. Also open the NBS 2023 bulletin Excel file for state-by-sex projections (D8), and confirm the WorldPop licence (D9).
3. **Author:** send the NBS email; then the P0 gate review. After that, P1 starts.

## Decisions log

| Date | Decision |
|---|---|
| 2026-10-16 | Revised plan adopted (`PLAN.md`): static site + DuckDB-WASM, two data zones, MPI 2021 as the main source. |
| 2026-10-16 | Chart library renamed `disability-access-charts` (`a11y-viz` unavailable on PyPI). |
| 2026-10-16 | JONAPWD ingest uses text extraction, not OCR. |
| 2026-10-16 | Applications describe the author as an independent researcher. |
