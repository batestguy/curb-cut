-- GRID3 health facilities by state (CC BY 4.0, docs/verification.md D57), typed.
select
    cast(state_code as varchar) as state_code,
    cast(facilities as integer) as facilities,
    cast(facilities_public as integer) as facilities_public,
    cast(facilities_ownership_unknown as integer) as facilities_ownership_unknown,
    cast(facilities_per_100k as double) as facilities_per_100k
from {{ source('spatial', 'facilities_state') }}
