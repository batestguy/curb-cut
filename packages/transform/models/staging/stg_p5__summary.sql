-- P5 scalar results (MPI and GHS) in one typed relation: value for numbers, value_text for
-- text items; suppressed counts keep a null value.
with unioned as (
    select * from {{ source('survey_aggregates', 'p5_mpi_summary') }}
    union all
    select * from {{ source('survey_aggregates', 'p5_ghs_summary') }}
)

select
    cast(source as varchar) as source,
    cast(dataset_version as varchar) as dataset_version,
    cast(analysis as varchar) as analysis,
    cast(section as varchar) as section,
    cast(item_id as varchar) as item_id,
    cast(label as varchar) as label,
    cast(kind as varchar) as kind,
    cast(nullif(value, '') as double) as value,
    nullif(cast(value_text as varchar), '') as value_text,
    cast(lower(suppressed) = 'true' as boolean) as suppressed
from unioned
