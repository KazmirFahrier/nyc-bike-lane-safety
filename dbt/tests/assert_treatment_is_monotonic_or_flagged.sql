-- Treatment should be absorbing: once a corridor has a protected lane it keeps
-- it, unless the lane was removed. A switch treated -> untreated is legitimate
-- only when the route file explains it -- either a later version dates the
-- replacement (has_dated_removal) or the record is Retired with no successor
-- and the end date is genuinely unknown (has_undated_removal). A switch
-- carrying neither means the treatment history is corrupt, not merely uncertain.
with seq as (
    select
        segmentid, panel_year, is_treated,
        has_undated_removal, has_dated_removal,
        lag(is_treated) over (partition by segmentid order by panel_year) as prev_treated
    from {{ ref('fct_segment_year_panel') }}
)
select segmentid, panel_year
from seq
where prev_treated and not is_treated
  and not has_undated_removal
  and not has_dated_removal
