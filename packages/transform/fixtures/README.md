# Synthetic fixture aggregates

`aggregates/` holds **invented** rows in exactly the schema the disclosure gate writes to `data/public/aggregates/`. No value comes from any survey. CI builds the warehouse on them in a separate DuckDB file (`--target fixtures`) to exercise edge cases the real files may not contain:

- a suppressed cell (Abia, DHS, DISABILITY3, ages 5–17: `n_unweighted` 12, numbers empty);
- a state with no rows at all (Zamfara is missing from `dhs2024_state.csv`), which must still appear in `mart_prevalence_state` with `has_data = false`;
- `review` (zero events) and `unreliable` (effective n under 30) flags;
- a suppressed zone cell in each GHS file;
- an MPI 2021 file, so the MPI model path is tested with edge cases too.

`tests/assert_fixture_edge_cases.sql` runs only in this build (`fixtures: true`). Command (from `packages/transform`):

```
uv run dbt build --profiles-dir . --target fixtures --vars '{aggregates_dir: fixtures/aggregates, include_mpi: true, mpi_aggregates_path: fixtures/aggregates/mpi2021_state_national.csv, fixtures: true}'
```
