with districts as (
    -- Notice we use `ref` instead of `source` here! 
    -- `ref` tells dbt to look for another dbt model or seed in our project.
    select * from {{ ref('bangkok_districts') }}
)

select
    -- The Thai name acts as our Primary Key
    district_th,
    district_en,
    zone as geographic_zone
from districts