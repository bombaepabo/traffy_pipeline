/* 
   A "Date Dimension" is a classic Data Engineering trick. 
   Instead of extracting the Year, Month, and Day in every single query, 
   we generate a static calendar table covering 10 years! 
*/
with date_spine as (
    select date_day
    from unnest(generate_date_array('2020-01-01', '2030-12-31')) as date_day
)

select
    date_day,
    extract(year from date_day) as year,
    extract(month from date_day) as month,
    extract(day from date_day) as day,
    extract(dayofweek from date_day) as day_of_week,
    
    -- In BigQuery, Day 1 is Sunday. Let's make a readable string.
    case extract(dayofweek from date_day)
        when 1 then 'Sunday'
        when 2 then 'Monday'
        when 3 then 'Tuesday'
        when 4 then 'Wednesday'
        when 5 then 'Thursday'
        when 6 then 'Friday'
        when 7 then 'Saturday'
    end as day_name
    
from date_spine