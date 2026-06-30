{{ config(
    materialized='view'
) }}

select
    ticket_id,
    created_date,
    district_th,
    category,
    status,
    
    -- Mask the exact street address. Keep the first 5 characters, replace the rest.
    CONCAT(SUBSTR(raw_address, 1, 5), '*** (Masked for PII)') as masked_address,
    
    -- We want them to build heatmaps, but let's round the GPS coordinates to 3 decimals
    -- This reduces the precision from a specific house down to a generic neighborhood block (approx 100 meters)
    ROUND(longitude, 3) as approx_longitude,
    ROUND(latitude, 3) as approx_latitude,
    
    has_flooding_issue,
    has_pothole_issue,
    has_dark_street_issue,
    has_garbage_issue,
    rating_star,
    reopen_count
    
-- Notice we reference the Fact table we just built!
from {{ ref('fact_complaints') }}