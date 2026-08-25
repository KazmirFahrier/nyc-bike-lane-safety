-- Every segment must appear in every panel year. An unbalanced panel would
-- make a segment's entry or exit look like a treatment effect.
select segmentid, count(*) as n_years
from {{ ref('fct_segment_year_panel') }}
group by segmentid
having count(*) <> ({{ var('study_end_year') }} - {{ var('study_start_year') }} + 1)
