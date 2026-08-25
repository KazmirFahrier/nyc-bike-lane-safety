{{ config(materialized='table') }}

-- Daily counter readings. The one piece of cleaning that happens here is
-- naming the offline case, because a dead counter and an empty street both
-- report zero and only one of them is data.

with src as (
    select * from {{ source('raw', 'bike_counts_daily') }}
)

select
    id                                    as counter_id,
    cast(day as date)                     as count_date,
    extract(year from cast(day as date))  as count_year,
    status                                as reading_status,
    cast(daily_counts as bigint)          as daily_counts,
    cast(intervals as integer)            as intervals,
    cast(nonzero_intervals as integer)    as nonzero_intervals,

    -- A full 96-interval day in which no interval ever recorded a single
    -- passage is a counter that was offline, not a street nobody rode.
    -- 4.0% of site-days. Counting these as zero ridership would inflate
    -- every per-rider injury rate computed downstream.
    (cast(intervals as integer) >= 96 and cast(nonzero_intervals as integer) = 0)
        as is_likely_offline

from src
