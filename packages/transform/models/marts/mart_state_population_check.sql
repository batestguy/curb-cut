-- NBS 2023 state projections (Annex 3) against WorldPop v3.0 (2025, scaled to UN WPP).
-- The years and national totals differ, so compare shares of the national total as well
-- as the raw difference (docs/verification.md D44).
with nbs as (
    select
        facts.state,
        facts.population_2023 as nbs_2023,
        sum(case when sex.sex = 'male' then sex.population_2023 end) as nbs_2023_male,
        sum(case when sex.sex = 'female' then sex.population_2023 end) as nbs_2023_female
    from {{ ref('state_facts') }} as facts
    left join {{ ref('state_population_by_sex_2023') }} as sex on facts.state = sex.state
    group by facts.state, facts.population_2023
),

joined as (
    select nbs.*, wp.population_2025 as worldpop_2025
    from nbs
    left join {{ ref('stg_worldpop__state_population') }} as wp on nbs.state = wp.state
)

select
    state,
    nbs_2023,
    nbs_2023_male,
    nbs_2023_female,
    worldpop_2025,
    (worldpop_2025 - nbs_2023) / nbs_2023 as pct_difference,
    nbs_2023 / sum(nbs_2023) over () as nbs_share,
    worldpop_2025 / sum(worldpop_2025) over () as worldpop_share,
    worldpop_2025 / sum(worldpop_2025) over () - nbs_2023 / sum(nbs_2023) over ()
        as share_difference
from joined
order by state
