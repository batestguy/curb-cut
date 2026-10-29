-- Every gated survey cell in one typed relation. MPI 2021 joins when include_mpi is true
-- (the default since its release on 2026-10-24). breakdown / breakdown_level name an
-- extra dimension (sector, wealth_quintile, age_band); both are 'all' where there is none.
{% set tables = ['dhs2024_state', 'dhs2024_national', 'dhs2024_zone', 'ghs_w4_national_zone', 'ghs_w5_national_zone'] %}
{% if var('include_mpi') %}
    {% do tables.append('mpi2021_state_national') %}
{% endif %}

with unioned as (
    {% for table in tables %}
    select * from {{ source('survey_aggregates', table) }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
),

typed as (
    select
        cast(source as varchar) as source,
        cast(dataset_version as varchar) as dataset_version,
        cast(measure as varchar) as measure,
        cast(geography_level as varchar) as geography_level,
        cast(geography as varchar) as geography,
        cast(age_group as varchar) as age_group,
        cast(sex as varchar) as sex,
        cast(breakdown as varchar) as breakdown,
        cast(breakdown_level as varchar) as breakdown_level,
        cast(nullif(estimate, '') as double) as estimate,
        cast(nullif(se, '') as double) as se,
        cast(nullif(ci_low, '') as double) as ci_low,
        cast(nullif(ci_high, '') as double) as ci_high,
        cast(n_unweighted as integer) as n_unweighted,
        cast(nullif(n_effective, '') as double) as n_effective,
        cast(nullif(df, '') as integer) as df,
        cast(precision_flag as varchar) as precision_flag,
        nullif(cast(precision_reason as varchar), '') as precision_reason,
        cast(lower(suppressed) = 'true' as boolean) as suppressed
    from unioned
)

select
    typed.*,
    states.state
from typed
left join {{ ref('dim_states') }} as states
    on typed.geography_level = 'state' and typed.geography = states.state_code
