with by_type as (
    select
        disability_type,
        cast(sum(persons) as bigint) as persons,
        count(distinct state) as states
    from {{ ref('stg_jonapwd__state_type') }}
    group by disability_type
)

select
    by_type.disability_type,
    types.display_label as disability_type_label,
    types.sort_order,
    by_type.persons,
    by_type.persons / sum(by_type.persons) over () as share_of_total,
    by_type.states
from by_type
inner join {{ ref('disability_types') }} as types on by_type.disability_type = types.disability_type
order by types.sort_order
