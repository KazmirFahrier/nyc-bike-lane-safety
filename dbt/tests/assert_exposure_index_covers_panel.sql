-- Every panel year from the exposure start onward needs an exposure value; a
-- null offset would silently drop that year from the negative binomial fit
-- rather than erroring. 2013 is exempt and explicitly flagged has_exposure =
-- false: the counter network did not exist, and the model does not invent a
-- number for it.
select panel_year
from {{ ref('fct_segment_year_panel') }}
where log_exposure is null
  and panel_year >= {{ var('exposure_start_year') }}
group by panel_year
