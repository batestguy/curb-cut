-- Breakdown levels: "all" exactly when the breakdown is "all"; otherwise one of the
-- breakdown's own levels. Age bands nest in their age group, and age bands are DISABILITY3
-- only and never by state. Only DHS has breakdowns.
select source, measure, geography_level, geography, age_group, sex, breakdown, breakdown_level
from {{ ref('stg_survey__aggregates') }}
where (breakdown = 'all') <> (breakdown_level = 'all')
    or (breakdown <> 'all' and source <> 'dhs2024')
    or (breakdown = 'sector' and breakdown_level not in ('urban', 'rural'))
    or (
        breakdown = 'wealth_quintile'
        and breakdown_level not in ('lowest', 'second', 'middle', 'fourth', 'highest')
    )
    or (
        breakdown = 'age_band'
        and (
            measure <> 'disability3'
            or geography_level = 'state'
            or (age_group = '5-17' and breakdown_level not in ('5-9', '10-14', '15-17'))
            or (
                age_group = '18+'
                and breakdown_level not in ('18-29', '30-39', '40-49', '50-59', '60-69', '70+')
            )
        )
    )
