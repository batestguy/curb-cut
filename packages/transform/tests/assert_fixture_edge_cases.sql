-- Fixture build only: the synthetic suppressed cell stays suppressed and null, the state
-- with no rows still appears in the mart with has_data = false, and the MPI fixture loads.
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
)

select * from checks where hits = 0
