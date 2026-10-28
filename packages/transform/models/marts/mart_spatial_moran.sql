-- Global Moran's I per measure with a plain label; DISABILITY3 18+ first, then the six
-- domains, then DISABILITY3 5-17 (secondary).
select
    moran.*,
    case moran.measure
        when 'disability3' then 'Disability (at least one domain)'
        when 'seeing_3plus' then 'Difficulty seeing'
        when 'hearing_3plus' then 'Difficulty hearing'
        when 'walking_3plus' then 'Difficulty walking or climbing steps'
        when 'cognition_3plus' then 'Difficulty remembering or concentrating'
        when 'selfcare_3plus' then 'Difficulty with self-care'
        when 'communication_3plus' then 'Difficulty communicating'
    end as measure_label,
    case moran.test_role when 'primary' then 1 when 'domain' then 2 else 3 end as sort_group
from {{ ref('stg_spatial__moran_global') }} as moran
order by sort_group, moran.measure
