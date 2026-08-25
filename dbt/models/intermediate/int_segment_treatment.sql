{{ config(materialized='table') }}

-- Reconstruct, per segment per year, whether an on-street protected lane was
-- actually in place -- rather than assuming the current snapshot held for the
-- whole twelve-year panel.
--
-- The route file has no retirement date. It has `status` ('Current' /
-- 'Retired') and a `prevbikeid` chain. So a record's validity ends when the
-- next record on the same segmentid begins. Where a Retired record has no
-- successor, the end date is genuinely unknown and is flagged rather than
-- guessed -- 439 protected segments are Retired, and treating a removed lane
-- as permanently treated would attribute post-removal crashes to the lane.

with versions as (
    select
        segmentid,
        street,
        boro_code,
        status,
        is_treated_facility,
        is_protected,
        is_onstreet,
        has_suspect_install_date,
        install_date                                                as valid_from,
        lead(install_date) over (
            partition by segmentid order by install_date, bikeid
        )                                                           as next_version_start
    from {{ ref('stg_bike_routes') }}
    where install_date is not null
),

spans as (
    select
        *,
        coalesce(next_version_start, date '9999-12-31')              as valid_to,
        -- A removal is *dated* when a later version on the same segment records
        -- what replaced the lane and when -- e.g. Broadway's 1978 protected lane
        -- superseded by a Shared facility on 2023-05-19. That is a known end,
        -- not a gap, and the panel should show the segment untreated from then.
        (is_treated_facility and next_version_start is not null)      as has_dated_removal,
        -- The case we genuinely cannot date: retired, with nothing recorded after.
        (status = 'Retired' and next_version_start is null)          as end_date_unknown
    from versions
),

years as (
    select unnest(generate_series(
        {{ "extract(year from date '" ~ var('study_start', '2013-01-01') ~ "')" }}::int,
        {{ "extract(year from date '" ~ var('study_end', '2024-12-31') ~ "')" }}::int
    )) as panel_year
),

-- 518 segmentids spell their street two ways across versions ("7 AV" on the
-- 2009 record, "7 AVENUE" on the 2024 one). Grouping on street would emit two
-- rows per segment-year and double-count every crash on them. Take the name
-- from the most recent version as canonical.
canonical as (
    select
        segmentid,
        first_value(street)    over w as street,
        first_value(boro_code) over w as boro_code
    from spans
    window w as (partition by segmentid order by valid_from desc, street)
    qualify row_number() over (partition by segmentid order by valid_from desc, street) = 1
),

segment_years as (
    select c.segmentid, c.street, c.boro_code, y.panel_year
    from canonical c
    cross join years y
),

treatment as (
    select
        sy.segmentid,
        sy.street,
        sy.boro_code,
        sy.panel_year,

        -- Treated in a year if an on-street protected version was in force at
        -- any point during it. A lane installed in June counts that year; the
        -- partial-year exposure is handled by the event-time indexing in the
        -- DiD, not by pretending the install happened in January.
        max(case
            when s.is_treated_facility
             and s.valid_from <= make_date(sy.panel_year, 12, 31)
             and s.valid_to   >  make_date(sy.panel_year, 1, 1)
            then 1 else 0
        end)::boolean                                               as is_treated,

        min(case when s.is_treated_facility then s.valid_from end)  as first_protected_date,
        max(case when s.end_date_unknown and s.is_treated_facility
                 then 1 else 0 end)::boolean                        as has_undated_removal,
        max(case when s.has_dated_removal then 1 else 0 end)::boolean as has_dated_removal,
        max(case when s.has_suspect_install_date and s.is_treated_facility
                 then 1 else 0 end)::boolean                        as has_suspect_install_date,
        max(case when s.is_protected and not s.is_onstreet
                 then 1 else 0 end)::boolean                        as is_offstreet_path

    from segment_years sy
    left join spans s on s.segmentid = sy.segmentid
    group by 1, 2, 3, 4
)

select
    *,
    extract(year from first_protected_date)                          as first_protected_year,

    -- Event time: years since the lane went in. Negative before, 0 in the
    -- install year. This is the axis the parallel-trends plot is drawn on.
    case when first_protected_date is not null
         then panel_year - extract(year from first_protected_date)
    end                                                              as years_since_treatment,

    -- Cohort membership for the staggered DiD.
    case
        when first_protected_date is null                            then 'never_treated'
        when extract(year from first_protected_date) < {{ var('study_start_year', 2013) }}
                                                                     then 'always_treated'
        when extract(year from first_protected_date) > {{ var('study_end_year', 2024) }}
                                                                     then 'treated_after_window'
        else 'switcher'
    end                                                              as treatment_cohort

from treatment
