# Current analysis scope

Updated October 1, 2026. This note describes the implementation used for the corrected analysis.

## Question and outcome

How do recorded cyclist injury counts change after protected bike lane installation, relative to matched comparison corridors? A separate descriptive analysis measures provision and installation timing across neighborhood demographic groups.

The primary outcome is injuries per street segment per year, aggregated to corridors. The study covers 2013 through 2024. It does not estimate injury risk per cyclist because local ridership is unobserved.

## Treatment

A corridor joins connected segments of the same street and borough with the same first installation year and complete annual treatment history. Known removals remain untreated in subsequent years. The standard staggered adoption design excludes corridors with nonabsorbing treatment or undated removals. Count models use recorded annual treatment and exclude undated removals. Descriptive outputs retain all corridors and mark whether a lane was ever recorded.

## Design

The staggered adoption analysis uses weighted group and time comparisons. Matching uses borough and injury counts in the three years before installation. It does not match street class or ridership. Cohorts start in 2018 so both the last preyear and earlier four year baseline have complete observations. Controls are never treated or not yet treated; common support and control weights are recalculated for each comparison year.

Poisson models include corridor and year fixed effects and corridor clustered standard errors. The common support specification restricts the sample and uses no regression weights. Pooled negative binomial results are descriptive associations. The TWFE comparison is an unweighted regression on the union of matched units and is not the same estimand as the group and time analysis.

## Exposure and equity

The automated counter index is a citywide proxy. Year fixed effects absorb it. No specification corrects for different ridership changes on treated streets. Growth at the selected counter sites does not establish growth in all NYC cycling.

Provision quintiles are defined over census tracts with observed demographics. Timing quintiles are defined over all corridors with observed demographics before restricting to treated corridors. They are distinct populations, clearly labeled, and fractional timing medians are preserved. Lane mileage describes facilities ever recorded as protected, not a verified current network. Tract demographics do not identify the riders using a corridor.

## Interpretation

This analysis does not establish a credible causal safety effect. Changes before installation are consistent with selection and other time varying factors; they do not prove why DOT selected a corridor. Event time averages can contain different cohorts. Null significance does not establish zero effect. Numerical agreement between implementations validates arithmetic, not causal assumptions.

See corrections.md for changes, reasons, validation, and remaining limits.
