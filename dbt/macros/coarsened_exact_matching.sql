{#
  Cohort-specific coarsened exact matching, shared by the corridor and segment
  panels so both are matched by exactly one implementation. A second copy of
  this logic would drift, and the two units would then differ for reasons
  nobody could reconstruct.

  Args:
    panel_relation : the ref() of the panel to match within
    unit_col       : 'corridor_id' or 'segmentid'
    first_cohort   : earliest cohort year with a full pre-window
#}
{% macro coarsened_exact_matching(panel_relation, unit_col, first_cohort) %}

with panel as (
    select * from {{ panel_relation }}
),

cohorts as (
    select distinct first_protected_year as cohort_year
    from panel
    where treatment_cohort = 'switcher'
      and first_protected_year >= {{ first_cohort }}
),

pre as (
    select
        c.cohort_year,
        p.{{ unit_col }}                                        as unit_id,
        any_value(p.boro_code)                                  as boro_code,
        sum(p.cyclist_injured)                                  as pre_injuries,
        count(*)                                                as pre_years
    from cohorts c
    join panel p
      on p.panel_year between c.cohort_year - 3 and c.cohort_year - 1
    group by 1, 2
),

status as (
    select
        c.cohort_year,
        p.{{ unit_col }}                                        as unit_id,
        max(case when p.treatment_cohort = 'switcher'
                  and p.first_protected_year = c.cohort_year
                 then 1 else 0 end)::boolean                    as is_treated_here,
        max(case when p.treatment_cohort = 'never_treated'
                  or coalesce(p.first_protected_year, 9999) > c.cohort_year
                 then 1 else 0 end)::boolean                    as is_eligible_control,
        max(case when p.treatment_cohort = 'always_treated'
                 then 1 else 0 end)::boolean                    as is_always_treated
    from cohorts c
    join panel p on true
    group by 1, 2
),

coarsened as (
    select
        pre.cohort_year,
        pre.unit_id,
        st.is_treated_here,
        st.is_eligible_control,
        pre.pre_injuries,
        pre.boro_code,
        case
            when pre.pre_injuries = 0 then '0'
            when pre.pre_injuries between 1 and 2 then '1-2'
            when pre.pre_injuries between 3 and 5 then '3-5'
            when pre.pre_injuries between 6 and 12 then '6-12'
            else '13+'
        end                                                     as injury_bin
    from pre
    join status st
      on st.cohort_year = pre.cohort_year and st.unit_id = pre.unit_id
    where not st.is_always_treated
),

strata as (
    select
        cohort_year, boro_code, injury_bin,
        count(*) filter (where is_treated_here)                             as n_treated,
        count(*) filter (where is_eligible_control and not is_treated_here) as n_control
    from coarsened
    group by 1, 2, 3
)

select
    c.cohort_year,
    c.unit_id,
    c.is_treated_here,
    c.is_eligible_control,
    c.boro_code,
    c.injury_bin,
    c.pre_injuries,
    s.n_treated,
    s.n_control,
    (s.n_treated > 0 and s.n_control > 0)                       as in_common_support,
    case
        when not (s.n_treated > 0 and s.n_control > 0) then 0.0
        when c.is_treated_here then 1.0
        when c.is_eligible_control then s.n_treated::double / s.n_control
        else 0.0
    end                                                         as cem_weight
from coarsened c
join strata s
  on s.cohort_year = c.cohort_year
 and s.boro_code   = c.boro_code
 and s.injury_bin  = c.injury_bin

{% endmacro %}
