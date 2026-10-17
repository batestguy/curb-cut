-- Every canonical state appears with every disability type exactly once.
with expected as (
    select s.state, t.disability_type
    from {{ ref('dim_states') }} as s
    cross join {{ ref('disability_types') }} as t
)

select e.state, e.disability_type
from expected as e
left join {{ ref('stg_jonapwd__state_type') }} as g
    on e.state = g.state and e.disability_type = g.disability_type
where g.state is null
