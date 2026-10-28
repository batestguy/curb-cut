-- The headline (DHS 2024 DISABILITY3, adults 18+, both sexes, no breakdown): one row per
-- state, every published one with an ordered 95% interval and a flag in the allowed set.
-- The fixture build leaves one state without rows on purpose.
{% set expected_missing = 1 if var('fixtures') else 0 %}
with headline as (
    select * from {{ ref('mart_prevalence_state') }}
    where source = 'dhs2024' and measure = 'disability3' and age_group = '18+' and sex = 'all'
),

checks as (
    select 'one row per state' as check_name,
        case when count(*) = 37 and count(distinct state_code) = 37 then 0 else 1 end as bad
    from headline
    union all
    select 'states with data',
        case when count(*) filter (where has_data) = 37 - {{ expected_missing }} then 0 else 1 end
    from headline
    union all
    select 'interval ordered', count(*)
    from headline
    where has_data and not suppressed and not (ci_low <= estimate and estimate <= ci_high)
    union all
    select 'flag allowed', count(*)
    from headline
    where precision_flag not in ('reliable', 'review', 'unreliable', 'suppressed', 'no_data')
)

select * from checks where bad > 0
