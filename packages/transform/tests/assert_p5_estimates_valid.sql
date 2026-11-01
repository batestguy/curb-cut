-- P5 estimates: every shown estimate lies inside its own 95% interval; a suppressed one has
-- its numbers and both group counts nulled; no shown estimate rests on a group under 30.
select estimate_id, estimate, ci_low, ci_high, n_exposed, n_unexposed, suppressed
from {{ ref('mart_p5_estimates') }}
where (
        not suppressed
        and (
            estimate is null or ci_low is null or ci_high is null
            or not (ci_low <= estimate and estimate <= ci_high)
            or n_exposed < 30 or n_unexposed < 30
        )
    )
    or (
        suppressed
        and (
            estimate is not null or ci_low is not null or ci_high is not null
            or n_exposed is not null or n_unexposed is not null
        )
    )
