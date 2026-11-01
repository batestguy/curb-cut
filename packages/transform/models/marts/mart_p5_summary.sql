-- P5 scalar results for the poverty page and brief (export_marts.py -> poverty.json).
select * from {{ ref('stg_p5__summary') }}
