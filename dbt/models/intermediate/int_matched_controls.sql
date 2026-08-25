{{ config(materialized='table') }}

-- Segment-level matching, kept as the robustness counterpart to
-- int_matched_corridors. Same macro, so the two units cannot drift apart.
-- The segment outcome is 92.5% zeros, which is why it is not the headline.

{{ coarsened_exact_matching(ref('fct_segment_year_panel'), 'segmentid', var('study_start_year') + 3) }}
