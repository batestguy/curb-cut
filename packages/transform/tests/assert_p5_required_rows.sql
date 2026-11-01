-- The poverty page and brief need these rows; each must exist exactly once (a missing one
-- would otherwise fail only at page build time).
with required as (
    select * from (values
        ('estimate', 'primary'), ('estimate', 'overlap_population'), ('estimate', 'survey_lpm'),
        ('estimate', 's1_score'), ('estimate', 's2_broad'), ('estimate', 's3_head'),
        ('estimate', 's4_health'), ('estimate', 's4_education'),
        ('estimate', 's4_living_standards'), ('estimate', 's4_work_and_shocks'),
        ('estimate', 's5_unasked_severe'), ('estimate', 's6_routing_free'),
        ('summary', 'table7_all_pass'), ('summary', 'evalue'), ('summary', 'rv'),
        ('summary', 'rva'), ('summary', 'placebo_empirical_p'), ('summary', 'rcc_pass'),
        ('summary', 'outside_weighted_share'), ('summary', 'osf_url'),
        ('summary', 'registered_utc'), ('summary', 'freeze_commit'),
        ('summary', 'linkage_rate'), ('summary', 'onset_cases')
    ) as t (kind, id)
),

present as (
    select 'estimate' as kind, estimate_id as id from {{ ref('mart_p5_estimates') }}
    union all
    select 'summary' as kind, item_id as id from {{ ref('mart_p5_summary') }}
)

select required.kind, required.id, count(present.id) as n
from required
left join present on required.kind = present.kind and required.id = present.id
group by required.kind, required.id
having count(present.id) <> 1
