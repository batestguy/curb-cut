-- State-level sources must cover all 37 states. The real build may have no state missing;
-- the fixture build leaves Zamfara out of the DHS file on purpose (exactly one per combo).
{% set expected_missing = 1 if var('fixtures') else 0 %}
with combos as (
    select
        source,
        measure,
        age_group,
        sex,
        count(*) filter (where not has_data) as states_without_data
    from {{ ref('mart_prevalence_state') }}
    where source = 'dhs2024'
    group by source, measure, age_group, sex
)

select * from combos where states_without_data <> {{ expected_missing }}
