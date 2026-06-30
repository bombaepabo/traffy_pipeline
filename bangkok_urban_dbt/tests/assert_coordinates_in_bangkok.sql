-- A custom dbt Singular Test.
-- This query should return ZERO rows. If it returns even one row, the dbt pipeline will fail.
-- It asserts that no GPS coordinates fall wildly outside of the Bangkok metropolitan area.

select
    ticket_id,
    latitude,
    longitude
from {{ ref('fact_complaints') }}
where 
    (latitude < 13.3 or latitude > 14.1)
    or 
    (longitude < 100.2 or longitude > 101.0)