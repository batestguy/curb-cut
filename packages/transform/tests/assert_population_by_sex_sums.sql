-- Annex 3: males + females must equal the state total already in state_facts.
select facts.state, facts.population_2023, sum(sex.population_2023) as by_sex
from {{ ref('state_facts') }} as facts
left join {{ ref('state_population_by_sex_2023') }} as sex on facts.state = sex.state
group by facts.state, facts.population_2023
having sum(sex.population_2023) is distinct from facts.population_2023
