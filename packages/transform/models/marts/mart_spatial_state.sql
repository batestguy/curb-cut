-- One row per state: the exploratory LISA class, the descriptive profile cluster and the
-- GRID3 facility rate, for the main page's spatial tables. DHS 2024 direct estimates only;
-- nothing spatial is ever computed on JONAPWD (docs/verification.md D17).
select
    states.state,
    states.state_code,
    states.zone,
    lisa.estimate as disability3_18plus,
    lisa.local_i,
    lisa.p_perm as lisa_p_perm,
    lisa.q_bh as lisa_q_bh,
    lisa.quadrant as lisa_quadrant,
    lisa.lisa_class,
    clusters.profile_cluster,
    facilities.facilities,
    facilities.facilities_per_100k
from {{ ref('dim_states') }} as states
inner join {{ ref('stg_spatial__lisa') }} as lisa on states.state_code = lisa.state_code
inner join {{ ref('stg_spatial__profile_clusters') }} as clusters
    on states.state_code = clusters.state_code
inner join {{ ref('stg_spatial__facilities') }} as facilities
    on states.state_code = facilities.state_code
order by states.state
