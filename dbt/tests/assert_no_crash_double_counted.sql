-- Each crash is assigned to exactly one segment. If the spatial join ever
-- emits a crash twice, segment-year counts inflate silently and every
-- estimate downstream is wrong in the same direction.
select collision_id, count(*) as n
from {{ ref('stg_crashes') }}
where segmentid is not null
group by collision_id
having count(*) > 1
