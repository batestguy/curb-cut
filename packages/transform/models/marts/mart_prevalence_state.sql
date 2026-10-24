-- One row per state x source x measure x age group x sex, for all 37 states even where a
-- source has no cell for a state (has_data = false). Suppressed cells keep null estimates.
-- Not shown on the site until P4.
with cells as (
    select * from {{ ref('stg_survey__aggregates') }}
    where geography_level = 'state'
),

combos as (
    select distinct source, dataset_version, measure, age_group, sex from cells
),

grid as (
    select states.state, states.state_code, states.zone, combos.*
    from {{ ref('dim_states') }} as states
    cross join combos
),

population as (
    select state, 'all' as sex, population_2023 from {{ ref('state_facts') }}
    union all
    select state, sex, population_2023 from {{ ref('state_population_by_sex_2023') }}
)

select
    grid.state,
    grid.state_code,
    grid.zone,
    grid.source,
    grid.dataset_version,
    grid.measure,
    grid.age_group,
    grid.sex,
    cells.estimate,
    cells.se,
    cells.ci_low,
    cells.ci_high,
    cells.n_unweighted,
    cells.n_effective,
    cells.df,
    coalesce(cells.precision_flag, 'no_data') as precision_flag,
    cells.precision_reason,
    coalesce(cells.suppressed, false) as suppressed,
    cells.measure is not null as has_data,
    population.population_2023
from grid
left join cells
    on grid.state_code = cells.geography
    and grid.source = cells.source
    and grid.measure = cells.measure
    and grid.age_group = cells.age_group
    and grid.sex = cells.sex
left join population
    on grid.state = population.state and grid.sex = population.sex
order by grid.source, grid.measure, grid.age_group, grid.sex, grid.state
