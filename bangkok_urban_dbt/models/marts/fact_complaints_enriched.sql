{{ config(materialized='table') }}

WITH unpivoted_tickets AS (
    -- UNPIVOT: One ticket can belong to multiple categories
    -- e.g. a ticket with both flooding AND pothole will appear twice
    SELECT 
        DATE(created_date) as complaint_date,
        ticket_id,
        complaint_type
    FROM {{ ref('mask_fact_complaints') }}
    CROSS JOIN UNNEST([
        STRUCT(has_flooding_issue AS flag, 'น้ำท่วม' AS complaint_type),
        STRUCT(has_pothole_issue, 'ถนน'),
        STRUCT(has_dark_street_issue, 'แสงสว่าง'),
        STRUCT(has_garbage_issue, 'ความสะอาด'),
        STRUCT(NOT (has_flooding_issue OR has_pothole_issue OR has_dark_street_issue OR has_garbage_issue), 'อื่นๆ')
    ]) AS categories
    WHERE categories.flag = TRUE
),

base_complaints AS (
    SELECT 
        complaint_date,
        complaint_type,
        COUNT(ticket_id) as total_complaints
    FROM unpivoted_tickets
    GROUP BY 1, 2
),

enriched_calendar AS (
    -- Read our new external dataset (Weather and Holidays)
    SELECT
        DATE(date) as calendar_date,
        precipitation_mm,
        max_temp_c,
        is_weekend,
        is_holiday
    FROM {{ ref('dim_date_enriched') }}
)

-- Join the internal complaints with the external weather factors
SELECT
    c.complaint_date as date,
    c.complaint_type,
    c.total_complaints,
    w.precipitation_mm,
    w.max_temp_c,
    w.is_weekend,
    w.is_holiday
FROM base_complaints c
JOIN enriched_calendar w
  ON c.complaint_date = w.calendar_date
ORDER BY c.complaint_date DESC
