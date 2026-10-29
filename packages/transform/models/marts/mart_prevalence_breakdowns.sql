-- Survey cells with an extra breakdown (urban/rural, wealth quintile, age band), at every
-- geography level. The other marts keep breakdown = 'all' only, so their grain is unchanged.
-- Suppressed cells keep null estimates; precision_flag says how far each can be trusted.
select
    source,
    dataset_version,
    measure,
    geography_level,
    geography,
    state,
    age_group,
    sex,
    breakdown,
    breakdown_level,
    estimate,
    se,
    ci_low,
    ci_high,
    n_unweighted,
    n_effective,
    df,
    precision_flag,
    precision_reason,
    suppressed
from {{ ref('stg_survey__aggregates') }}
where breakdown <> 'all'
order by source, geography_level, geography, breakdown, breakdown_level, measure, age_group
