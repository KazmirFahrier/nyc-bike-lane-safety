-- Each segment belongs to exactly one corridor. A segment in two corridors
-- would double-count its crashes at the corridor level.
select segmentid, count(distinct corridor_id) as n
from {{ source('interim', 'segment_corridors') }}
group by segmentid
having count(distinct corridor_id) > 1
