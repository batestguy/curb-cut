-- One row per state for the state card: zone, facts, and the state's JONAPWD total with
-- its share of the all-state total and its rank (1 = largest).
with state_totals as (
    select state, cast(sum(persons) as bigint) as jonapwd_total
    from {{ ref('stg_jonapwd__state_type') }}
    group by state
)

select
    states.state,
    states.state_code,
    states.zone,
    facts.capital,
    facts.capital_source_url,
    nullif(facts.slogan, '') as slogan,
    nullif(facts.slogan_source_url, '') as slogan_source_url,
    facts.population_2023,
    state_totals.jonapwd_total,
    state_totals.jonapwd_total / sum(state_totals.jonapwd_total) over () as share_of_national,
    cast(rank() over (order by state_totals.jonapwd_total desc) as integer) as rank_of_37
from {{ ref('dim_states') }} as states
inner join {{ ref('state_facts') }} as facts on states.state = facts.state
inner join state_totals on states.state = state_totals.state
order by states.state
