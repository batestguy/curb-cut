-- Complementary suppression, re-tested in the warehouse: in any set of cells that add up
-- (a breakdown's levels; women and men; states within Nigeria and within their zone; zones
-- within Nigeria), exactly one suppressed cell could be recovered by subtraction from the
-- total. Every such partition must hold zero or at least two suppressed cells. Also, no
-- suppressed cell may show its unweighted count. The ingest gate does the same
-- (curbcut_ingest.disclosure.complementary); this is the independent check.
with cells as (
    select a.*, s.zone as state_zone
    from {{ ref('stg_survey__aggregates') }} as a
    left join {{ ref('dim_states') }} as s
        on a.geography_level = 'state' and a.geography = s.state_code
),

partitions as (
    select 'breakdown' as kind, source, measure, geography_level, geography, age_group, sex,
        breakdown as part, count(*) filter (where suppressed) as hidden, count(*) as cells
    from cells where breakdown <> 'all'
    group by all
    union all
    select 'sex', source, measure, geography_level, geography, age_group,
        breakdown || ':' || breakdown_level, null, count(*) filter (where suppressed), count(*)
    from cells where sex <> 'all'
    group by all
    union all
    select 'states in Nigeria', source, measure, 'state', null, age_group, sex,
        breakdown || ':' || breakdown_level, count(*) filter (where suppressed), count(*)
    from cells where geography_level = 'state'
    group by all
    union all
    select 'states in zone', source, measure, 'state', state_zone, age_group, sex,
        breakdown || ':' || breakdown_level, count(*) filter (where suppressed), count(*)
    from cells where geography_level = 'state'
    group by all
    union all
    select 'zones in Nigeria', source, measure, 'zone', null, age_group, sex,
        breakdown || ':' || breakdown_level, count(*) filter (where suppressed), count(*)
    from cells where geography_level = 'zone'
    group by all
)

select kind, source, measure, geography_level, geography, age_group, sex, part,
    hidden, cells, null::integer as n_unweighted
from partitions
where hidden = 1 and cells > 1
union all
select 'count shown on a suppressed cell', source, measure, geography_level, geography,
    age_group, sex, breakdown || ':' || breakdown_level, 1, 1, n_unweighted
from cells
where suppressed and n_unweighted is not null
