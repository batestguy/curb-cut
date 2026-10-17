with staged as (
    select * from {{ ref('stg_jonapwd__state_type') }}
),

state_totals as (
    select state, cast(sum(persons) as bigint) as state_total
    from staged
    group by state
)

select
    staged.state,
    states.state_code,
    states.zone,
    staged.disability_type,
    types.display_label as disability_type_label,
    types.sort_order,
    staged.persons,
    state_totals.state_total,
    staged.persons / state_totals.state_total as share_of_state,
    staged.source_page
from staged
inner join {{ ref('dim_states') }} as states on staged.state = states.state
inner join {{ ref('disability_types') }} as types on staged.disability_type = types.disability_type
inner join state_totals on staged.state = state_totals.state
order by staged.state, types.sort_order
