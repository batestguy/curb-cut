-- NDHS 2024 report Table 14.1 as transcribed (percentages), typed.
select
    cast("row" as varchar) as row_id,
    cast(no_difficulty as double) as no_difficulty,
    cast("some" as double) as some_difficulty,
    cast(a_lot as double) as a_lot,
    cast(cannot as double) as cannot,
    cast(dont_know as double) as dont_know,
    cast(a_lot_or_cannot as double) as a_lot_or_cannot,
    cast("number" as bigint) as weighted_number
from {{ source('ndhs_report', 'fr395_table14_1') }}
