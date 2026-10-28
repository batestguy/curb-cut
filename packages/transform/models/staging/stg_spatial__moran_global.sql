-- Global Moran's I per measure (DHS 2024 direct state estimates), typed.
select
    cast(measure as varchar) as measure,
    cast(age_group as varchar) as age_group,
    cast("role" as varchar) as test_role,
    cast(moran_i as double) as moran_i,
    cast(expected_i as double) as expected_i,
    cast(p_perm as double) as p_perm,
    cast(p_bh as double) as p_bh,
    cast(nsim as integer) as nsim,
    cast(n_states as integer) as n_states,
    cast(n_reliable as integer) as n_reliable,
    cast(n_review as integer) as n_review,
    cast(n_unreliable as integer) as n_unreliable,
    cast(n_zero_estimate as integer) as n_zero_estimate,
    cast(n_imprecise as integer) as n_imprecise
from {{ source('spatial', 'moran_global') }}
