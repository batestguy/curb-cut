-- WorldPop v3.0 state totals with canonical state names (alias seed).
with source as (
    select
        cast(statename as varchar) as state_as_printed,
        cast(population as double) as population_2025
    from {{ source('worldpop', 'states_pop_total_scaled') }}
),

state_keys as (
    select {{ normalise_state_key('state') }} as state_key, state
    from {{ ref('dim_states') }}
    union
    select {{ normalise_state_key('alias') }} as state_key, state
    from {{ ref('state_name_aliases') }}
)

select
    source.state_as_printed,
    state_keys.state,
    source.population_2025
from source
left join state_keys
    on {{ normalise_state_key('source.state_as_printed') }} = state_keys.state_key
