-- The spatial outputs cover exactly the 37 states, and the LISA estimate is the headline
-- direct estimate it was computed from (the committed aggregates; not the fixtures).
{{ config(enabled=not var('fixtures')) }}
with s as (select * from {{ ref('mart_spatial_state') }}),

headline as (
    select state_code, estimate from {{ ref('mart_prevalence_state') }}
    where source = 'dhs2024' and measure = 'disability3' and age_group = '18+' and sex = 'all'
),

checks as (
    select 'thirty-seven states' as check_name,
        case when count(*) = 37 then 0 else 1 end as bad
    from s
    union all
    select 'lisa estimate is the direct estimate', count(*)
    from s inner join headline on s.state_code = headline.state_code
    where abs(s.disability3_18plus - headline.estimate) > 1e-9
)

select * from checks where bad > 0
