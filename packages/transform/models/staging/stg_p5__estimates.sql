-- P5 model estimates (MPI and GHS) in one typed relation. Proportions or 0-1 score points
-- as the gate wrote them; suppressed rows keep null numbers.
with unioned as (
    select * from {{ source('survey_aggregates', 'p5_mpi_estimates') }}
    union all
    select * from {{ source('survey_aggregates', 'p5_ghs_estimates') }}
)

select
    cast(source as varchar) as source,
    cast(dataset_version as varchar) as dataset_version,
    cast(analysis as varchar) as analysis,
    cast("group" as varchar) as estimate_group,
    cast(estimate_id as varchar) as estimate_id,
    cast(label as varchar) as label,
    cast(outcome as varchar) as outcome,
    cast(exposure as varchar) as exposure,
    cast(scale as varchar) as scale,
    nullif(cast(learners as varchar), '') as learners,
    cast(nullif(estimate, '') as double) as estimate,
    cast(nullif(se, '') as double) as se,
    cast(nullif(ci_low, '') as double) as ci_low,
    cast(nullif(ci_high, '') as double) as ci_high,
    cast(nullif(pval, '') as double) as pval,
    cast(nullif(holm_p, '') as double) as holm_p,
    case lower(supported) when 'true' then true when 'false' then false end as supported,
    cast(nullif(mu0, '') as double) as mu0,
    cast(n as integer) as n,
    cast(nullif(n_exposed, '') as integer) as n_exposed,
    cast(nullif(n_unexposed, '') as integer) as n_unexposed,
    cast(lower(suppressed) = 'true' as boolean) as suppressed
from unioned
