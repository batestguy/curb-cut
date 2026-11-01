-- P5 estimates for the poverty page and brief (export_marts.py -> poverty.json). Adds the
-- display scale: x100 turns proportions into percentage points and 0-1 scores into points
-- out of 100; GHS log consumption stays in log points.
select
    estimates.*,
    case when estimates.outcome = 'dlog_consumption' then 1 else 100 end as display_factor,
    case estimates.estimate_group
        when 'headline' then 1
        when 'secondary' then 2
        when 'dimension' then 3
        when 'robustness' then 4
        when 'leave_one_zone_out' then 5
        when 'subgroup' then 6
        when 'sensemakr' then 7
        when 'e1' then 8
        when 'r_check' then 9
    end as group_order
from {{ ref('stg_p5__estimates') }} as estimates
