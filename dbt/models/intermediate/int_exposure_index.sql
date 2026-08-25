{{ config(materialized='table') }}

-- A citywide cycling exposure index from DOT's automated counters.
--
-- The naive version of this model is badly wrong, and it is worth saying how,
-- because the error is invisible in the output unless you look:
--
--   Requiring only that a site "reports in every year" admitted 7 sites whose
--   2013 coverage was 13-37 days. The index then read 100 in 2013 and 3004 in
--   2014 -- a 30x apparent ridership explosion that is entirely an artefact of
--   the counter network being switched on. Used as an offset, it would have
--   swamped every treatment effect in the study.
--
-- Two fixes, both structural:
--
-- 1. **Chained index, not a fixed cohort.** Growth is computed for each
--    consecutive year pair using only sites well-observed in *both* years,
--    then chained. A site that comes online in 2019 contributes to growth
--    from 2019 onward and never registers as a citywide jump. This uses far
--    more of the data than a balanced cohort while remaining immune to
--    composition change.
--
-- 2. **Deduplicated sensors.** Two locations are instrumented twice under
--    different ids -- "Manhattan Bridge Display Bike Counter" (100047029) and
--    "Manhattan Bridge Bike Comprehensive" (100062893) share coordinates and
--    report identical daily totals on 2,338 days; likewise Brooklyn Bridge
--    (300020241 / 300020904). Summing both double-counts those crossings,
--    which are among the highest-volume in the city.
--
-- The index starts in {{ var('exposure_start_year') }}: 2013 has 262 usable
-- site-days citywide, and no site clears 50. There is no ridership measurement
-- for 2013, so the model does not invent one.

with daily as (
    select * from {{ ref('stg_bike_counts') }}
    where not is_likely_offline
      and counter_id not in ({{ "'" ~ var('duplicate_counter_ids') | join("','") ~ "'" }})
),

site_years as (
    select
        counter_id,
        count_year,
        sum(daily_counts)          as annual_counts,
        count(distinct count_date) as days_reporting
    from daily
    group by 1, 2
),

-- "Well observed" = enough of the year that a seasonal cycling series is
-- meaningful. Cycling volume is strongly seasonal, so a site covering only
-- summer would overstate its year.
observed as (
    select * from site_years
    where days_reporting >= {{ var('min_days_per_site_year') }}
      and count_year >= {{ var('exposure_start_year') }}
),

-- Year-over-year growth on the sites common to each adjacent pair.
pairs as (
    select
        b.count_year                              as panel_year,
        count(*)                                  as sites_in_link,
        sum(b.annual_counts)                      as counts_this_year,
        sum(a.annual_counts)                      as counts_prior_year,
        sum(b.annual_counts)::double
            / nullif(sum(a.annual_counts), 0)     as link_growth
    from observed b
    join observed a
      on a.counter_id = b.counter_id
     and a.count_year = b.count_year - 1
    group by 1
),

chained as (
    select
        panel_year,
        sites_in_link,
        counts_this_year,
        counts_prior_year,
        link_growth,
        exp(sum(ln(link_growth)) over (order by panel_year
             rows between unbounded preceding and current row)) as cum_growth
    from pairs
),

indexed as (
    select
        {{ var('exposure_start_year') }} as panel_year,
        null::bigint                     as sites_in_link,
        null::double                     as link_growth,
        1.0                              as cum_growth
    union all
    select panel_year, sites_in_link, link_growth, cum_growth from chained
)

select
    panel_year,
    sites_in_link,
    link_growth,
    100.0 * cum_growth                as ridership_index,
    ln(cum_growth)                    as log_exposure
from indexed
order by panel_year
