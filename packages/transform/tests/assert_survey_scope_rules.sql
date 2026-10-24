-- Scope rules: GHS is never below zone level, and MPI 2021 measures always carry the mpi_
-- prefix and are never DISABILITY3 (its module is not the WG-SS; verification.md D39, D43).
select source, measure, geography_level, geography
from {{ ref('stg_survey__aggregates') }}
where (source like 'ghs%' and geography_level not in ('national', 'zone'))
    or (source = 'mpi2021' and (measure = 'disability3' or not starts_with(measure, 'mpi_')))
