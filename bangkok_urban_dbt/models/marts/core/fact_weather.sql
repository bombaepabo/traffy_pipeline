{{ config(
    materialized='table'
) }}

with weather as (
    select * from {{ ref('stg_weather') }}
)

select
    weather_date,
    rainfall_mm,
    temp_max_c,
    temp_min_c,
    humidity_max
from weather