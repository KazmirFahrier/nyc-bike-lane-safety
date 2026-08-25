{{ config(materialized='table') }}

-- The analysis panel: one row per street segment per year, carrying treatment
-- status, cyclist injury counts, and the exposure term.
--
-- Contested crashes -- those the spatial join could not assign a treatment
-- status to non-arbitrarily -- are excluded when include_contested_crashes is
-- false (the default). They are 13.4% of matched crashes, so this is a real
-- choice, and D9 re-runs the estimate with them included.

with treatment as (
    select * from {{ ref('int_segment_treatment') }}
),

crashes as (
    select
        segmentid,
        crash_year,
        count(*)                        as crash_count,
        sum(cyclist_injured)            as cyclist_injured,
        sum(cyclist_killed)             as cyclist_killed,
        sum(cyclist_injured + cyclist_killed) as cyclist_ksi_proxy,
        sum(case when assignment_contested then 1 else 0 end) as contested_crashes
    from {{ ref('stg_crashes') }}
    where segmentid is not null
      {% if not var('include_contested_crashes') %}
      and not assignment_contested
      {% endif %}
    group by 1, 2
),

exposure as (
    select * from {{ ref('int_exposure_index') }}
)

select
    t.segmentid,
    t.panel_year,
    t.street,
    t.boro_code,

    t.is_treated,
    t.treatment_cohort,
    t.first_protected_year,
    t.facility_in_force,
    t.years_since_treatment,

    coalesce(c.crash_count, 0)        as crash_count,
    coalesce(c.cyclist_injured, 0)    as cyclist_injured,
    coalesce(c.cyclist_killed, 0)     as cyclist_killed,
    coalesce(c.cyclist_ksi_proxy, 0)  as cyclist_ksi_proxy,

    e.ridership_index,
    e.log_exposure,
    e.log_exposure is not null   as has_exposure,

    -- Quality flags travel with the panel so no downstream model can use a
    -- row without being able to see what is wrong with it.
    t.has_undated_removal,
    t.has_dated_removal,
    t.has_suspect_install_date,
    t.is_offstreet_path,
    coalesce(c.contested_crashes, 0)  as contested_crashes_excluded

from treatment t
left join crashes c
       on c.segmentid = t.segmentid
      and c.crash_year = t.panel_year
left join exposure e
       on e.panel_year = t.panel_year

-- Off-street paths are neither treatment nor control: they are not streets.
where not t.is_offstreet_path
