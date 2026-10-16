# Data

Two zones, because NBS / World Bank / DHS licences forbid republishing household-level microdata.

- `restricted/` — **git-ignored, local only.** Licensed microdata (NBS MPI 2021, GHS-Panel). Never commit it, and never send it to an LLM or any external service.
- Public aggregates — produced from the restricted zone by scripts that apply a disclosure check (cells under ~30 unweighted respondents are suppressed) and write a provenance manifest (source, version, licence, suppression count).

CI never sees restricted data; it runs on synthetic fixtures with the same schema.
