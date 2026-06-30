with raw_complaints as (
    select * from {{ source('bangkok_raw', 'ext_complaints') }}
)

select
    -- Primary Key
    cast(ticket_id as string) as ticket_id,
    
    -- Timestamps
    cast(timestamp as timestamp) as created_at,
    cast(timestamp as date) as created_date,
    
    -- Dimensions
    cast(category as string) as category,
    cast(district_khet as string) as district_th,
    cast(state as string) as status,
    
    -- PII / Details
    cast(description as string) as description,
    cast(address as string) as raw_address,
    
    -- Geospatial
    cast(lon as float64) as longitude,
    cast(lat as float64) as latitude,
    
    -- NLP Flags (Booleans)
    cast(has_flooding_issue as boolean) as has_flooding_issue,
    cast(has_pothole_issue as boolean) as has_pothole_issue,
    cast(has_dark_street_issue as boolean) as has_dark_street_issue,
    cast(has_garbage_issue as boolean) as has_garbage_issue,
    
    -- Metrics
    cast(rating_star as int64) as rating_star,
    cast(reopen_count as int64) as reopen_count

from raw_complaints
-- Filter out entirely null rows that sometimes come from empty Parquet files
where ticket_id is not null
  -- Block any records that our Spark Spatial Join couldn't map to a Bangkok polygon
  and district_khet != 'Unknown'