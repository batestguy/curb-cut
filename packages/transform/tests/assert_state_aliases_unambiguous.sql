-- A normalised alias must point at one canonical state only.
select {{ normalise_state_key('alias') }} as state_key
from {{ ref('state_name_aliases') }}
group by 1
having count(distinct state) > 1
