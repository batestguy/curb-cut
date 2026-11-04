# Synthetic fixture aggregates

`aggregates/` holds **invented** rows in exactly the schema the disclosure gate writes to `data/public/aggregates/`. No value comes from any survey. CI builds the warehouse on them in a separate DuckDB file (`--target fixtures`) to exercise edge cases the real files may not contain:

- a suppressed cell (Abia, DHS, DISABILITY3, ages 5–17: `n_unweighted` 12, numbers empty);
- a state with no rows at all (Zamfara is missing from `dhs2024_state.csv`), which must still appear in `mart_prevalence_state` with `has_data = false`;
- `review` (zero events) and `unreliable` (effective n under 30) flags;
- a suppressed zone cell in each GHS file;
- an MPI 2021 file, so the MPI model path is tested with edge cases too;
- P5 model estimates and summaries (`p5_mpi_estimates.csv`, `p5_mpi_summary.csv`, `p5_ghs_estimates.csv`, `p5_ghs_summary.csv`, written by `curbcut_ingest.disclosure` from invented results): one X1 subgroup suppressed for too few exposed households, a suppressed summary count, a dimension interval that crosses zero and a secondary that is not supported;
- the `breakdown` / `breakdown_level` columns on every file (`all` / `all` where there is no extra breakdown), with state-by-sex rows for 36 states (Zamfara still missing), a DHS zone file (`dhs2024_zone.csv`, including a suppressed zone cell), and at least one row per breakdown (`sector`, `wealth_quintile`, `age_band`), including a suppressed breakdown cell (Abia, rural).

`tests/assert_fixture_edge_cases.sql` runs only in this build (`fixtures: true`). Command (from `packages/transform`):

```
uv run dbt build --profiles-dir . --target fixtures --vars '{aggregates_dir: fixtures/aggregates, include_mpi: true, mpi_aggregates_path: fixtures/aggregates/mpi2021_state_national.csv, fixtures: true}'
```

Because every value is invented, these files carry no survey licence terms: they are part of the repository (MIT) and must never be cited or used as estimates.
