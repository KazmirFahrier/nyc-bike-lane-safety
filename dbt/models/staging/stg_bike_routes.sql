{{ config(materialized='table') }}

-- One row per route-record version. A single segmentid can carry several
-- versions over time (a conventional lane later upgraded to protected, a
-- protected lane later retired), which is what makes treatment timing
-- reconstructable in int_segment_treatment.

with src as (
    -- The source carries exact-duplicate version rows for some segments
    -- (segmentid 0033879 has its 1978 Protected record twice). Left in, they
    -- would weight those segments twice in every aggregate.
    select distinct * from {{ source('raw', 'bike_routes') }}
)

select
    segmentid,
    nullif(bikeid, '')                          as bikeid,
    nullif(prevbikeid, 'NA')                    as prevbikeid,
    upper(trim(street))                         as street,
    nullif(trim(boro), '')                      as boro_code,
    status,
    onoffst,
    facilitycl,
    nullif(ft_facilit, '')                      as ft_facility,
    nullif(tf_facilit, '')                      as tf_facility,
    cast(instdate as date)                      as install_date,
    extract(year from cast(instdate as date))   as install_year,

    cast(is_protected          as boolean)      as is_protected,
    cast(is_onstreet           as boolean)      as is_onstreet,
    cast(is_treated_facility   as boolean)      as is_treated_facility,

    -- Install dates before 1990 are inherited from the underlying street
    -- centerline, not from any bike facility. 403 protected segments carry
    -- them (1894, 1900, 1909...). Flagged, never silently dropped.
    cast(instdate as date) < date '1990-01-01'  as has_suspect_install_date,

    geometry_wkt

from src
