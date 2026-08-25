-- The injury total in the panel must equal the injury total among the crashes
-- that fed it. This is the end-to-end check: it catches a bad join, a dropped
-- year, or a filter that silently removed rows between staging and the mart.
with staged as (
    select sum(cyclist_injured) as n
    from {{ ref('stg_crashes') }}
    where segmentid is not null
      and crash_year between {{ var('study_start_year') }} and {{ var('study_end_year') }}
      {% if not var('include_contested_crashes') %}
      and not assignment_contested
      {% endif %}
      and segmentid in (
          select segmentid from {{ ref('int_segment_treatment') }}
          where not is_offstreet_path
      )
),
panel as (
    select sum(cyclist_injured) as n from {{ ref('fct_segment_year_panel') }}
)
select staged.n as staged_injuries, panel.n as panel_injuries
from staged cross join panel
where staged.n is distinct from panel.n
