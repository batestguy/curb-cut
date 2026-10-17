-- The national mart must add up to the source rows, with nothing lost in joins.
select n.total, s.total
from (select sum(persons) as total from {{ ref('mart_jonapwd_national_by_type') }}) as n
cross join (select sum(cast(persons as bigint)) as total from {{ source('jonapwd', 'state_disability_type') }}) as s
where n.total is distinct from s.total
