-- The main page's comparison: verified figures only (author, 2026-10-28). JONAPWD's assumed
-- 15% and WHO's global 16% (seed reference_figures); the NDHS 2024 report's Table 14.1 for
-- ages 15+, "any difficulty" (computed here as 100 - no difficulty - don't know) against the
-- Washington Group cut-off; and our DHS 2024 direct estimate for adults 18+ with its 95%
-- interval. The spec's unsourced "10-18%" range is not included.
with ndhs as (
    select * from {{ ref('stg_ndhs_report__table14_1') }} where row_id = 'age_15_plus'
),

ours as (
    select * from {{ ref('mart_prevalence_national_zone') }}
    where
        source = 'dhs2024' and measure = 'disability3' and geography_level = 'national'
        and age_group = '18+' and sex = 'all' and not suppressed
),

report_source as (
    select
        'Nigeria DHS 2023-24 final report (NPC and ICF, FR395), Table 14.1, p. 443' as source,
        'https://dhsprogram.com/pubs/pdf/FR395/FR395.pdf' as source_url
)

select
    figure_id,
    sort_order,
    label,
    kind,
    value_percent,
    cast(null as double) as ci_low_percent,
    cast(null as double) as ci_high_percent,
    population,
    definition,
    source,
    source_url
from {{ ref('reference_figures') }}

union all

select
    'ndhs2024_15plus_any',
    3,
    'NDHS 2024 report: any difficulty',
    'measured',
    round(100 - ndhs.no_difficulty - ndhs.dont_know, 1),
    null,
    null,
    'Household members aged 15+ (de facto)',
    'At least some difficulty in at least one of the six Washington Group domains '
    || '(100% minus "no difficulty" minus "don''t know").',
    report_source.source,
    report_source.source_url
from ndhs cross join report_source

union all

select
    'ndhs2024_15plus_wg',
    4,
    'NDHS 2024 report: Washington Group cut-off',
    'measured',
    ndhs.a_lot_or_cannot,
    null,
    null,
    'Household members aged 15+ (de facto)',
    '"A lot of difficulty" or "cannot do at all" in at least one domain (the Washington '
    || 'Group disability cut-off).',
    report_source.source,
    report_source.source_url
from ndhs cross join report_source

union all

select
    'dhs2024_18plus_wg',
    5,
    'Curb Cut: DHS 2024, adults 18+',
    'measured',
    round(100 * ours.estimate, 1),
    round(100 * ours.ci_low, 1),
    round(100 * ours.ci_high, 1),
    'Household members aged 18+ (de facto)',
    'Washington Group DISABILITY3: "a lot of difficulty" or "cannot do at all" in at least '
    || 'one domain. Our own estimate from the DHS microdata, with its 95% confidence interval.',
    'The DHS Program, Nigeria DHS 2024 (NPC and ICF); Curb Cut estimate',
    'https://github.com/batestguy/curb-cut/tree/main/data/public/aggregates'
from ours

order by sort_order
