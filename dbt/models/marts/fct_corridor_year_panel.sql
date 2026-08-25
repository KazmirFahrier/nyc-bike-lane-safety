{{ config(materialized='table') }}

-- The primary analysis panel: one row per corridor per year.
--
-- Corridor rather than segment, for reasons set out in nycbike.corridors:
-- 92.5% of segment-years are zero, DOT installs lanes on corridors rather than
-- blocks, and most intersection-assignment ambiguity is between adjacent
-- blocks of the same corridor and dissolves under aggregation.
--
-- The segment panel is kept and still tested. It is the robustness spec, not
-- the headline, and D9 reports both.

with seg_panel as (
    select * from {{ ref('fct_segment_year_panel') }}
),

map as (
    select segmentid, corridor_id from {{ source('interim', 'segment_corridors') }}
),

joined as (
    select m.corridor_id, p.*
    from seg_panel p
    join map m on m.segmentid = p.segmentid
)

select
    corridor_id,
    panel_year,

    any_value(street)                       as street,
    any_value(boro_code)                    as boro_code,
    count(distinct segmentid)               as n_segments,

    -- Treatment is a corridor-level property by construction: the corridor was
    -- split on treatment history, so every segment in it shares one.
    bool_or(is_treated)                     as is_treated,
    any_value(treatment_cohort)             as treatment_cohort,
    any_value(first_protected_year)         as first_protected_year,
    any_value(years_since_treatment)        as years_since_treatment,

    sum(crash_count)                        as crash_count,
    sum(cyclist_injured)                    as cyclist_injured,
    sum(cyclist_killed)                     as cyclist_killed,
    sum(cyclist_ksi_proxy)                  as cyclist_ksi_proxy,

    any_value(ridership_index)              as ridership_index,
    any_value(log_exposure)                 as log_exposure,
    any_value(has_exposure)                 as has_exposure,

    -- Corridor length in segments is the offset's scale term: a 30-block
    -- corridor has ten times the opportunity for a crash as a 3-block one, and
    -- the model must not read that as ten times the risk.
    ln(count(distinct segmentid))           as log_segments,

    bool_or(has_undated_removal)            as has_undated_removal,
    bool_or(has_suspect_install_date)       as has_suspect_install_date,
    sum(contested_crashes_excluded)         as contested_crashes_excluded

from joined
group by corridor_id, panel_year
