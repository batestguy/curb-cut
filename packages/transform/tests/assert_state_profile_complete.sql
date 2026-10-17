-- The state card needs all 37 states, shares that add up to the whole, a source for every
-- slogan, and totals that match the national mart.
with profile as (
    select
        count(*) as n,
        sum(share_of_national) as share_sum,
        sum(jonapwd_total) as total,
        count(*) filter (where (slogan is null) <> (slogan_source_url is null)) as unsourced
    from {{ ref('mart_state_profile') }}
),

national as (
    select sum(persons) as total from {{ ref('mart_jonapwd_national_by_type') }}
)

select profile.*, national.total as national_total
from profile cross join national
where profile.n <> 37
    or abs(profile.share_sum - 1) > 1e-9
    or profile.unsourced > 0
    or profile.total is distinct from national.total
