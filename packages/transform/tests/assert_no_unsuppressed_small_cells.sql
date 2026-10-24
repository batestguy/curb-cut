-- Disclosure check, re-tested in the warehouse: no cell under 30 unweighted respondents
-- may carry an estimate, and every suppressed cell must have its numbers nulled.
select source, measure, geography_level, geography, age_group, sex, n_unweighted
from {{ ref('stg_survey__aggregates') }}
where (n_unweighted < 30 and not suppressed)
    or (
        suppressed
        and (
            estimate is not null or se is not null or ci_low is not null
            or ci_high is not null or n_effective is not null or df is not null
            or precision_flag <> 'suppressed'
        )
    )
    or (not suppressed and estimate is null)
