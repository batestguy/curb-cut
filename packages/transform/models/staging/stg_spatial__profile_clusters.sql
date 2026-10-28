-- Descriptive profile clusters (one row per state), typed.
select
    cast(geography as varchar) as state_code,
    cast("cluster" as integer) as profile_cluster
from {{ source('spatial', 'profile_clusters') }}
