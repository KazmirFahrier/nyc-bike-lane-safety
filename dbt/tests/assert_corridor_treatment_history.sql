-- Connected segments in a corridor must agree on annual treatment status.
select m.corridor_id, p.panel_year
from {{ ref('fct_segment_year_panel') }} p
join {{ source('interim', 'segment_corridors') }} m using (segmentid)
group by m.corridor_id, p.panel_year
having count(distinct p.is_treated) > 1
