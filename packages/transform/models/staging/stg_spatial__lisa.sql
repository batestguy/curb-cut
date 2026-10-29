-- Exploratory LISA for DISABILITY3 18+ (one row per state), typed.
select
    cast(geography as varchar) as state_code,
    cast(estimate as double) as estimate,
    cast(local_i as double) as local_i,
    cast(p_perm as double) as p_perm,
    cast(q_bh as double) as q_bh,
    cast(quadrant as varchar) as quadrant,
    cast(lisa_class as varchar) as lisa_class
from {{ source('spatial', 'lisa_disability3_18plus') }}
