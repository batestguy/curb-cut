-- The comparison's NDHS "any difficulty" figure is 100 - no difficulty - don't know for ages
-- 15+, recomputed here from the transcription; the WG cut-off figure is the report's own
-- column; our interval is ordered around the estimate; every expected figure is present.
-- The 10-18% range from the spec must never come back.
with ndhs as (
    select * from {{ ref('stg_ndhs_report__table14_1') }} where row_id = 'age_15_plus'
),

c as (select * from {{ ref('mart_prevalence_comparison') }}),

checks as (
    select 'ndhs any difficulty' as check_name, count(*) as bad
    from c cross join ndhs
    where c.figure_id = 'ndhs2024_15plus_any'
        and abs(c.value_percent - (100 - ndhs.no_difficulty - ndhs.dont_know)) > 0.05
    union all
    select 'ndhs wg cut-off', count(*)
    from c cross join ndhs
    where c.figure_id = 'ndhs2024_15plus_wg' and c.value_percent <> ndhs.a_lot_or_cannot
    union all
    select 'our interval ordered', count(*)
    from c
    where c.figure_id = 'dhs2024_18plus_wg'
        and not (c.ci_low_percent <= c.value_percent and c.value_percent <= c.ci_high_percent)
    union all
    select 'five figures', case when count(*) = 5 then 0 else 1 end from c
    union all
    select 'no 10-18 range', count(*) from c where lower(c.label || c.definition) like '%10%18%'
)

select * from checks where bad > 0
