-- Aggregating segments into corridors must not create or lose a single injury.
-- If the corridor map misses segments, or maps one segment to two corridors,
-- the totals diverge and every corridor-level estimate is built on a different
-- dataset than the segment-level one it is compared against.
with seg as (
    select sum(p.cyclist_injured) as n
    from {{ ref('fct_segment_year_panel') }} p
    join {{ source('interim', 'segment_corridors') }} m on m.segmentid = p.segmentid
),
cor as (
    select sum(cyclist_injured) as n from {{ ref('fct_corridor_year_panel') }}
)
select seg.n as segment_injuries, cor.n as corridor_injuries
from seg cross join cor
where seg.n is distinct from cor.n
