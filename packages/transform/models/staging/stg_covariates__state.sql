-- Fay-Herriot state covariates (raw, unstandardised), typed. C4 is women 15-49 (D53).
-- wp2020_pop_total and wp2020_pop_18plus are benchmark weights, not covariates.
select
    cast(state as varchar) as state,
    cast(state_code as varchar) as state_code,
    cast(c1_share_60plus as double) as c1_share_60plus,
    cast(c2_urban_share as double) as c2_urban_share,
    cast(c3_mpi_headcount as double) as c3_mpi_headcount,
    cast(c4_female_literacy as double) as c4_female_literacy,
    cast(c5_log_density as double) as c5_log_density,
    cast(population_2023 as bigint) as population_2023,
    cast(area_km2 as double) as area_km2,
    cast(wp2020_pop_total as bigint) as wp2020_pop_total,
    cast(wp2020_pop_18plus as bigint) as wp2020_pop_18plus
from {{ source('covariates', 'state_covariates') }}
