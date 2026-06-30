with raw_weather as (
    select * from {{ source('bangkok_raw', 'ext_weather') }}
)

select
    -- Primary Key (Date)
    cast(date as date) as weather_date,
    
    -- Metrics
    cast(rainfall_mm as float64) as rainfall_mm,
    cast(temp_max_c as float64) as temp_max_c,
    cast(temp_min_c as float64) as temp_min_c,
    cast(humidity_max as float64) as humidity_max

from raw_weather
where date is not null
