{{ config(
    materialized='table',
    unique_key='ticket_id'
) }}

with complaints as (
    select * from {{ ref('stg_complaints') }}
)

select
    -- Foreign Keys to our Dimensions
    created_date,
    district_th,
    
    -- The core event data
    ticket_id,
    created_at,
    category,
    status,
    description,
    raw_address,
    longitude,
    latitude,
    has_flooding_issue,
    has_pothole_issue,
    has_dark_street_issue,
    has_garbage_issue,
    rating_star,
    reopen_count
from complaints