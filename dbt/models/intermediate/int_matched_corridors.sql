{{ config(materialized='table') }}

-- Matched comparison corridors -- the primary design.
--
-- DOT does not install lanes at random, and the selection is not even in the
-- same direction everywhere: Manhattan corridors that got lanes were already
-- running 0.575 pre-period injuries against 0.416 on those that did not, while
-- in the Bronx the treated corridors were the *safer* ones (0.128 vs 0.172).
-- A pooled comparison would net those against each other and look unbiased
-- while being wrong in both boroughs.
--
-- Each treated corridor is compared only to corridors in the same borough with
-- a similar recent injury history, matched on its own three years before
-- treatment. Corridors first treated 2013-2015 have no full pre-window and are
-- excluded from the matched design; they remain in the unmatched robustness spec.

{{ coarsened_exact_matching(ref('fct_corridor_year_panel'), 'corridor_id', var('study_start_year') + 3) }}
