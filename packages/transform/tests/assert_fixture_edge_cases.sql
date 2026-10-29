-- Fixture build only: the synthetic suppressed cell stays suppressed and null, the state
-- with no rows still appears in the mart with has_data = false, the MPI fixture loads, the
-- DHS zone file and state-by-sex rows load, and breakdown rows reach only their own mart.
{{ config(enabled=var('fixtures')) }}
with checks as (
    select 'suppressed cell kept null' as check_name, count(*) as hits
    from {{ ref('mart_prevalence_state') }}
    where state_code = 'NG-AB' and source = 'dhs2024' and measure = 'disability3'
        and age_group = '5-17' and suppressed and estimate is null
        and precision_flag = 'suppressed'
    union all
    select 'empty state present', count(*)
    from {{ ref('mart_prevalence_state') }}
    where state_code = 'NG-ZA' and source = 'dhs2024' and not has_data
    union all
    select 'mpi fixture loaded', count(*)
    from {{ ref('stg_survey__aggregates') }}
    where source = 'mpi2021'
    union all
    select 'dhs zone file loaded', count(*)
    from {{ ref('mart_prevalence_national_zone') }}
    where source = 'dhs2024' and geography_level = 'zone' and geography = 'North West'
    union all
    select 'state by sex in state mart', count(*)
    from {{ ref('mart_prevalence_state') }}
    where state_code = 'NG-AB' and source = 'dhs2024' and sex = 'female' and has_data
    union all
    select 'suppressed breakdown cell kept null', count(*)
    from {{ ref('mart_prevalence_breakdowns') }}
    where geography = 'NG-AB' and breakdown = 'sector' and breakdown_level = 'rural'
        and suppressed and estimate is null and state = 'Abia'
    {% for breakdown in ['sector', 'wealth_quintile', 'age_band'] %}
    union all
    select 'breakdown {{ breakdown }} present', count(*)
    from {{ ref('mart_prevalence_breakdowns') }}
    where breakdown = '{{ breakdown }}'
    {% endfor %}
    union all
    -- inverted: a breakdown row must never reach the state mart
    select 'no breakdown rows in state mart', case when count(*) = 0 then 1 else 0 end
    from {{ ref('mart_prevalence_state') }}
    where state_code = 'NG-AB' and source = 'dhs2024' and measure = 'disability3'
        and age_group = '18+' and sex = 'all' and estimate is null
)

select * from checks where hits = 0
