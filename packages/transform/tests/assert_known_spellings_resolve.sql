-- Spellings seen in JONAPWD, NBS, geoBoundaries, survey value labels (MPI, DHS, GHS) and WorldPop must all resolve to a canonical state.
-- Uses the same matching as stg_jonapwd__state_type.
with spellings (raw, expected) as (
    values
        ('Abia state', 'Abia'),
        ('Cross river', 'Cross River'),
        ('CROSS-RIVER', 'Cross River'),
        ('FCT Abuja', 'Federal Capital Territory'),
        ('FCT', 'Federal Capital Territory'),
        ('FEDERAL CAPITAL TERRITORY', 'Federal Capital Territory'),
        ('Akwa Ibom ', 'Akwa Ibom'),
        ('Akwa-Ibom', 'Akwa Ibom'),
        ('AKWA IBOM', 'Akwa Ibom'),
        ('Abuja Federal Capital Territory', 'Federal Capital Territory'),
        ('FCT ABUJA', 'Federal Capital Territory'),
        ('fct', 'Federal Capital Territory'),
        ('37. FCT', 'Federal Capital Territory'),
        ('Federal Capital', 'Federal Capital Territory'),
        ('Cross-River', 'Cross River'),
        ('25. Nasarawa', 'Nasarawa'),
        ('plateau', 'Plateau')
),

state_keys as (
    select {{ normalise_state_key('state') }} as state_key, state from {{ ref('dim_states') }}
    union
    select {{ normalise_state_key('alias') }} as state_key, state from {{ ref('state_name_aliases') }}
)

select spellings.raw, spellings.expected, state_keys.state as resolved
from spellings
left join state_keys on {{ normalise_state_key('spellings.raw') }} = state_keys.state_key
where state_keys.state is distinct from spellings.expected
