{{ config(materialized='table') }}

-- Cyclist-injury crashes, typed and joined to their assigned street segment.
-- Socrata serves every column as text; all casting happens here so the raw
-- layer stays a faithful copy of the API response.

with src as (
    select * from {{ source('interim', 'crashes_segments') }}
)

select
    cast(collision_id as bigint)                      as collision_id,
    cast(crash_date as timestamp)                     as crash_ts,
    cast(crash_date as date)                          as crash_date,
    extract(year from cast(crash_date as timestamp))  as crash_year,
    nullif(trim(borough), '')                         as borough,

    cast(latitude  as double)                         as latitude,
    cast(longitude as double)                         as longitude,

    coalesce(cast(number_of_cyclist_injured as integer), 0) as cyclist_injured,
    coalesce(cast(number_of_cyclist_killed  as integer), 0) as cyclist_killed,
    coalesce(cast(number_of_persons_injured as integer), 0) as persons_injured,
    coalesce(cast(number_of_persons_killed  as integer), 0) as persons_killed,

    -- Spatial assignment, carried forward with its provenance so every
    -- downstream model can filter on how the crash got here.
    segmentid,
    cast(d_ft as double)                              as dist_to_centerline_ft,
    assignment_method,
    coalesce(cast(assignment_contested as boolean), false) as assignment_contested,
    segmentid is null                                 as is_off_panel

from src
