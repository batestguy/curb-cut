# Data

Two zones, because NBS / World Bank / DHS licences forbid republishing household-level microdata.

- `restricted/` — **git-ignored, local only.** Licensed microdata (NBS MPI 2021, Nigeria DHS 2024, GHS-Panel W4/W5) and the harmonised person-level files in `restricted/derived/`. Never commit it, and never send it to an LLM or any external service.
- `public/aggregates/` — survey aggregates written only by the disclosure gate (`packages/ingest/src/curbcut_ingest/disclosure.py`): cells under 30 unweighted respondents are suppressed, every row has an NCHS precision flag, and `manifest.json` records source, version, terms, hash, script commit and suppression count. MPI 2021 aggregates are held in the git-ignored `public/aggregates/mpi2021/` until NBS replies. How to rebuild: `docs/reproduce.md`.

CI never sees restricted data; it runs on synthetic fixtures with the same schema.
