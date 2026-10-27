-- National and zone cells from every source (GHS is national/zone only by design), with no
-- extra breakdown (those are in mart_prevalence_breakdowns).
select
    source,
    dataset_version,
    measure,
    geography_level,
    geography,
    age_group,
    sex,
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
where geography_level in ('national', 'zone') and breakdown = 'all'
order by source, geography_level, geography, measure, age_group, sex
