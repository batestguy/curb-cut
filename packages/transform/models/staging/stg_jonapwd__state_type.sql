with source as (
    select
        cast(state as varchar) as state,
        cast(disability_type as varchar) as disability_type,
        cast(disability_type_label as varchar) as disability_type_label,
        cast(persons as bigint) as persons,
        cast(source_page as integer) as source_page
    from {{ source('jonapwd', 'state_disability_type') }}
),

-- Canonical names match themselves; the alias seed covers other spellings.
state_keys as (
    select {{ normalise_state_key('state') }} as state_key, state
    from {{ ref('dim_states') }}
    union
    select {{ normalise_state_key('alias') }} as state_key, state
    from {{ ref('state_name_aliases') }}
)

select
    source.state as state_as_printed,
    state_keys.state,
    source.disability_type,
    source.disability_type_label as source_label,
    source.persons,
    source.source_page
from source
left join state_keys
    on {{ normalise_state_key('source.state') }} = state_keys.state_key
