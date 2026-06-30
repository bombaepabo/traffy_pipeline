{{ config(
    materialized='incremental',
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

-- This block only runs on subsequent days, NOT on the first run!
{% if is_incremental() %}
  -- Only process new rows that are newer than what we already have stored in this table
  where created_at > (select max(created_at) from {{ this }})
{% endif %}