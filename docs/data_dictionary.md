# Data dictionary

*Generated from the built warehouse. Regenerate with `python scripts/gen_data_dictionary.py` after `make dbt`.*

## Sources, as pulled

Every pull is reconciled before it is written. Row pulls are checked against the server's own `count(*)`; aggregate pulls have no cheap group count, so they are checked against control totals computed over the ungrouped data.

| Source | Dataset | Rows landed | Reconciled against | Pulled |
|---|---|---|---|---|
| `bike_counters` | `smn3-rzf9` | 41 | server `count(*)` = 41 | 2026-08-25 |
| `bike_counts` | `uczf-rk3c` | 65,162 | `daily_counts` = 159,183,214; `intervals` = 6,208,848 | 2026-08-25 |
| `bike_routes` | `mzxg-pwib` | 29,695 | server `count(*)` = 29,695 | 2026-08-25 |
| `crashes` | `h9gi-nx95` | 57,353 | server `count(*)` = 57,353 | 2026-08-25 |

## Tables

### `fct_corridor_year_panel`

`main.fct_corridor_year_panel` — 26,808 rows

| Column | Type |
|---|---|
| `corridor_id` | VARCHAR |
| `panel_year` | BIGINT |
| `street` | VARCHAR |
| `boro_code` | VARCHAR |
| `n_segments` | BIGINT |
| `is_treated` | BOOLEAN |
| `treatment_cohort` | VARCHAR |
| `first_protected_year` | BIGINT |
| `years_since_treatment` | BIGINT |
| `crash_count` | HUGEINT |
| `cyclist_injured` | HUGEINT |
| `cyclist_killed` | HUGEINT |
| `cyclist_ksi_proxy` | HUGEINT |
| `ridership_index` | DOUBLE |
| `log_exposure` | DOUBLE |
| `has_exposure` | BOOLEAN |
| `log_segments` | DOUBLE |
| `has_undated_removal` | BOOLEAN |
| `has_suspect_install_date` | BOOLEAN |
| `contested_crashes_excluded` | HUGEINT |

### `fct_segment_year_panel`

`main.fct_segment_year_panel` — 245,268 rows

| Column | Type |
|---|---|
| `segmentid` | VARCHAR |
| `panel_year` | BIGINT |
| `street` | VARCHAR |
| `boro_code` | VARCHAR |
| `is_treated` | BOOLEAN |
| `treatment_cohort` | VARCHAR |
| `first_protected_year` | BIGINT |
| `facility_in_force` | VARCHAR |
| `years_since_treatment` | BIGINT |
| `crash_count` | BIGINT |
| `cyclist_injured` | HUGEINT |
| `cyclist_killed` | HUGEINT |
| `cyclist_ksi_proxy` | HUGEINT |
| `ridership_index` | DOUBLE |
| `log_exposure` | DOUBLE |
| `has_exposure` | BOOLEAN |
| `has_undated_removal` | BOOLEAN |
| `has_dated_removal` | BOOLEAN |
| `has_suspect_install_date` | BOOLEAN |
| `is_offstreet_path` | BOOLEAN |
| `contested_crashes_excluded` | HUGEINT |

### `int_exposure_index`

`main.int_exposure_index` — 11 rows

| Column | Type |
|---|---|
| `panel_year` | BIGINT |
| `sites_in_link` | BIGINT |
| `link_growth` | DOUBLE |
| `ridership_index` | DOUBLE |
| `log_exposure` | DOUBLE |

### `int_matched_controls`

`main.int_matched_controls` — 175,725 rows

| Column | Type |
|---|---|
| `cohort_year` | BIGINT |
| `unit_id` | VARCHAR |
| `is_treated_here` | BOOLEAN |
| `is_eligible_control` | BOOLEAN |
| `boro_code` | VARCHAR |
| `injury_bin` | VARCHAR |
| `pre_injuries` | HUGEINT |
| `n_treated` | BIGINT |
| `n_control` | BIGINT |
| `in_common_support` | BOOLEAN |
| `cem_weight` | DOUBLE |

### `int_matched_corridors`

`main.int_matched_corridors` — 19,188 rows

| Column | Type |
|---|---|
| `cohort_year` | BIGINT |
| `unit_id` | VARCHAR |
| `is_treated_here` | BOOLEAN |
| `is_eligible_control` | BOOLEAN |
| `boro_code` | VARCHAR |
| `injury_bin` | VARCHAR |
| `pre_injuries` | HUGEINT |
| `n_treated` | BIGINT |
| `n_control` | BIGINT |
| `in_common_support` | BOOLEAN |
| `cem_weight` | DOUBLE |

### `int_segment_treatment`

`main.int_segment_treatment` — 297,360 rows

| Column | Type |
|---|---|
| `segmentid` | VARCHAR |
| `street` | VARCHAR |
| `boro_code` | VARCHAR |
| `panel_year` | BIGINT |
| `is_treated` | BOOLEAN |
| `first_protected_date` | DATE |
| `facility_in_force` | VARCHAR |
| `has_undated_removal` | BOOLEAN |
| `has_dated_removal` | BOOLEAN |
| `has_suspect_install_date` | BOOLEAN |
| `is_offstreet_path` | BOOLEAN |
| `first_protected_year` | BIGINT |
| `years_since_treatment` | BIGINT |
| `treatment_cohort` | VARCHAR |

### `stg_bike_counts`

`main_staging.stg_bike_counts` — 65,162 rows

| Column | Type |
|---|---|
| `counter_id` | VARCHAR |
| `count_date` | DATE |
| `count_year` | BIGINT |
| `reading_status` | VARCHAR |
| `daily_counts` | BIGINT |
| `intervals` | INTEGER |
| `nonzero_intervals` | INTEGER |
| `is_likely_offline` | BOOLEAN |

### `stg_bike_routes`

`main_staging.stg_bike_routes` — 29,607 rows

| Column | Type |
|---|---|
| `segmentid` | VARCHAR |
| `bikeid` | VARCHAR |
| `prevbikeid` | VARCHAR |
| `street` | VARCHAR |
| `boro_code` | VARCHAR |
| `status` | VARCHAR |
| `onoffst` | VARCHAR |
| `facilitycl` | VARCHAR |
| `ft_facility` | VARCHAR |
| `tf_facility` | VARCHAR |
| `install_date` | DATE |
| `install_year` | BIGINT |
| `is_protected` | BOOLEAN |
| `is_onstreet` | BOOLEAN |
| `is_treated_facility` | BOOLEAN |
| `has_suspect_install_date` | BOOLEAN |
| `geometry_wkt` | VARCHAR |

### `stg_crashes`

`main_staging.stg_crashes` — 53,080 rows

| Column | Type |
|---|---|
| `collision_id` | BIGINT |
| `crash_ts` | TIMESTAMP |
| `crash_date` | DATE |
| `crash_year` | BIGINT |
| `borough` | VARCHAR |
| `latitude` | DOUBLE |
| `longitude` | DOUBLE |
| `cyclist_injured` | INTEGER |
| `cyclist_killed` | INTEGER |
| `persons_injured` | INTEGER |
| `persons_killed` | INTEGER |
| `segmentid` | VARCHAR |
| `dist_to_centerline_ft` | DOUBLE |
| `assignment_method` | VARCHAR |
| `assignment_contested` | BOOLEAN |
| `is_off_panel` | BOOLEAN |

## Known data-quality issues

These are carried as flags in the panel rather than cleaned away, so no
downstream model can use a row without being able to see what is wrong with it.

| Issue | Scale | Where it is flagged |
|---|---|---|
| Crash records with no usable coordinates | 4,273 of 57,353 (7.5%); geocoding rate ranges 86.3% (2016) to 94.8% (2023) | dropped at the spatial join, counted in `spatial_join_qa` |
| Crashes whose nearest two centerlines disagree on treatment | 3,911 of 29,113 matched (13.4%) | `assignment_contested` |
| "Protected" segments with install dates before 1990 (1894, 1900, 1909) | 403 | `has_suspect_install_date` |
| Protected segments retired with no successor to date the removal | 439 | `has_undated_removal` |
| Counter readings with undocumented `status=4` | 1,253,944 of 6,208,848 readings (20.2%) in 2013 through 2024, carrying 24.0% of measured passages | kept as a grouping key, never silently included or excluded |
| Counter site-days that are 96 intervals of zero (offline, not empty) | 4.0% of site-days | `is_likely_offline` |
| Two bridges instrumented twice under different ids | Manhattan Bridge (100047029/100062893) identical on 2,338 days; Brooklyn Bridge (300020241/300020904) | `duplicate_counter_ids` var |
| No ridership measurement for 2013 | 262 usable site-days citywide, no site clearing 50 | `has_exposure` |
