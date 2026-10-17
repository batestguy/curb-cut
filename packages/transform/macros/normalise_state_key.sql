{#- Matching key for state names: letters only, single-spaced, lower case.
    'CROSS-RIVER', 'Cross river' and 'Akwa Ibom ' (trailing space) all normalise cleanly. -#}
{% macro normalise_state_key(column) -%}
    lower(trim(regexp_replace({{ column }}, '[^A-Za-z]+', ' ', 'g')))
{%- endmacro %}
