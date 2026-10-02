# October 2026 correction record

Updated October 1, 2026. This correction replaces the original published analysis and explains what changed, why it mattered, and how the corrected computation was checked.

## What changed in the results

| Published quantity | Before correction | Corrected run |
|---|---:|---:|
| Descriptive corridors | 2,234 | 2,244 |
| Corridors first treated during 2013 through 2024 | 519 | 523 |
| Treated corridors in the matched design | 472 | 383 |
| Staggered adoption, last preyear | −17.7% | −30.6%, interval −78.0% to +8.8% |
| Staggered adoption, earlier prewindow | +8.0% | −4.2%, interval −30.6% to +20.0% |
| Poisson on common support | +12.1% | +21.3%, interval +2.0% to +44.3% |

The corrected estimates jointly reflect changes to treatment histories, eligibility, cohort windows, time specific support, Poisson sample coverage and weighting. This table does not isolate the contribution of any individual correction. The old Poisson regression used maximum cohort weights; the corrected specification is an unweighted restriction to the common support population. The old count sample omitted 2013; the corrected sample retains it. These changes are part of the specification change and are not evidence of a new policy effect.

The primary estimates are additive injury differences divided by the matched treated sample's observed preperiod mean. The Poisson percentage is exp(coefficient) minus one. These are different estimands and sample definitions. Their percentages should not be read as directly comparable causal safety effects.

The original claims that the preperiod baseline reverses the estimate's sign and that every specification is indistinguishable from zero have been withdrawn. The two corrected staggered adoption intervals include zero. The common support Poisson interval is above zero. The analysis does not establish that lanes cause harm or safety benefits.

## 1. Annual treatment and corridor construction

**What was wrong.** The count models rebuilt treatment as every year after the first installation, even where the panel recorded a later removal. The previous exported panel contained 101 contradictory corridor years across 18 corridors. Corridors were also grouped only by street, borough and first installation year, which could combine segments with different subsequent treatment histories.

**What changed.** Count models use the recorded annual `is_treated` flag. Connected segments are now grouped by their complete annual treatment trajectory as well as street, borough and first year. The corrected panel contains 2,244 corridors instead of 2,234. Its injury totals are conserved. Fourteen corridors with undated removal histories are excluded from model estimation. The standard absorbing treatment design also excludes all corridors whose recorded status contradicts continued treatment after installation; the descriptive panel retains them.

**Why.** A removed lane must not be coded as continuing treatment. Standard staggered adoption assumes treatment persists; removals require either a different estimator or an explicit sample restriction. Combining different histories hides the relevant distinction.

**Checked by.** A new dbt test requires all segments in each corridor to agree on treatment in every year. Regression tests verify removed and undated lanes are excluded from the absorbing sample and that count models preserve recorded removals. PostGIS and Python give the same partition of all 20,439 segments.

## 2. Exposure and the meaning of the outcome

**What was wrong.** The opening question implied that the models adjusted for ridership growing specifically on treated streets. Only a citywide index was available. Its year only variation is absorbed by year fixed effects. Requiring nonmissing exposure additionally discarded 2013, although no distinct exposure correction was identified.

**What changed.** The redundant citywide offset was removed, 2013 retained, and the counter index labeled as a descriptive network proxy. The reports now call the outcomes recorded injury counts, not risk per rider. The constant corridor size offset remains; corridor effects also absorb its fixed scale.

**Why.** A citywide proxy cannot account for differential ridership changes. An offset that is collinear with year effects does not supply the missing local denominator. Growth at selected counters does not establish growth in all NYC cycling.

**Checked by.** The live pull reconciled both 6,208,848 readings and 159,183,214 passages. A regression test verifies 2013 remains eligible despite missing counter exposure. Limitations include incomplete site coverage, seasonality and unmeasured local ridership.

## 3. Matching, changing controls and baseline coverage

**What was wrong.** The README listed ridership and street class as matching variables, although the implementation used only borough and prior injury counts. Initial cohort weights were retained after future treated controls left, potentially changing the represented mix of strata. The earlier four year baseline had incomplete observations for early cohorts. Poisson weights took the maximum across different cohort comparisons, which has no single documented cohort target.

**What changed.** The explanation now matches the actual variables. Each group and time cell recomputes common support and control weights, dropping unsupported treated strata. Both baseline choices use cohorts beginning in 2018, ensuring observations for all five preperiod years. The common support Poisson regression uses an unweighted sample restriction. The supplementary TWFE regression is explicitly unweighted and is not claimed to estimate the same quantity as the group and time estimator.

**Why.** Changing controls can invalidate weights calibrated to the original control population. Comparing incomplete baseline windows mixes different preperiod definitions. Arbitrarily collapsing distinct cohort weights obscures the regression's target population.

**Checked by.** A known arithmetic example checks control weights after a future treated control leaves. Block bootstrap multiplicities preserve whole corridor histories and recompute support within each draw. The bootstrap is calculated in batches with 1,000 draws and a fixed seed. Corridor IDs are sorted before assigning draws, so database row order cannot change the confidence intervals. The first fresh checkout caught this ordering defect; a regression test now shuffles both inputs and requires identical draws. All 77 Python group and time estimates agree with the independent R implementation within 3.1 × 10⁻¹⁶. This validates computation, not parallel trends or causal identification.

## 4. Equity definitions and medians

**What was wrong.** The dashboard recomputed quintiles within treated corridors, whereas the analysis and brief used quintiles over all corridors with demographics. It also truncated fractional timing medians to integers. Under the former dashboard grouping, 2021.5 became 2021, conflicting with the brief's 2022.

**What changed.** One shared timing function reuses the existing population quintiles before restricting to treated corridors. Medians are stored as floats and rendered without truncation. The report distinguishes tract quintiles for provision from corridor demographic quintiles for timing. Under the corrected population groups, the poorest and most POC corridor quintiles both have a median installation year of 2022, compared with 2019 for the richest and least POC groups.

**Why.** A subgroup should not silently be reranked into a different demographic classification. Fractional medians are real summaries, not malformed years. Tract and corridor groups represent different populations.

**Checked by.** A regression test preserves an assigned quintile and a 2021.5 median. The publication validator requires dashboard timing records to equal the shared summary of the corridor file. Reports describe mileage ever recorded as protected, including removed lanes, and identify ecological and missing demographic limitations.

## 5. Reproduction and publication consistency

**What was wrong.** `make all` did not run the count model script, so it could reuse committed outputs. The web brief contained an independent hardcoded narrative and estimate table; its equity conclusion was stale. The dashboard also typed in the numerical preperiod baseline. The clean room check did not fail on every quantitative disagreement, and its 50 draw run did not reproduce the published intervals. The README reported 39 dbt tests, although the previous project actually defined 31. The data dictionary also confused 439 retired route records with the 134 unique protected segments whose removal remained undated.

**What changed.** The build includes count models, model generated baselines, shared report generation and both brief formats. README results and the landing page are generated from the model exports. PDF and web briefs read the same rendered Markdown, authored from a report template. The publication builder rejects fewer than 1,000 bootstrap draws. The clean room script clones an explicitly selected branch into an empty directory, runs the full publication pipeline and compares model estimates and intervals to the committed reference; differences fail with an instruction to inspect receipts and versions. It no longer deletes an existing target directory. The data dictionary is regenerated after the warehouse build, and its undated removal count is queried from the model.

**Why.** A successful script must mean the current models generated the reported result. Separate numerical and narrative copies drift. Tests and arithmetic checks should fail when their stated conditions do not hold.

**Checked by.** The local run passes 46 Python tests, 32 dbt data tests and lint. The publication validator compares model estimates, baseline normalization, timing groups, generated report text and inlined dashboard data. The five page PDF was rendered and visually inspected. Sources, environment versions, code hashes and validation summaries are recorded in `analysis/output/run_manifest.json`. The fresh checkout result is recorded in the pull request after completion.

## 6. Interpretation and remaining uncertainty

Statements that injury changes prove why DOT installed lanes, that observational data can never answer the question, and that every estimate includes zero were replaced with narrower claims supported by this analysis. Differences across specifications combine conditioning and sample changes, rather than measuring the selection mechanism directly.

This analysis does not establish a credible causal safety effect. Remaining limits include reconstructed dates, undated retirements, reported and geocoded crashes, local ridership, annual treatment during partial installation years, changing cohort composition in event plots, Poisson separation and ecological demographics. A mean preperiod bootstrap test is not a joint parallel trends test. Pointwise event intervals are not simultaneous bands.

The correction preserves these limits instead of treating numerical agreement or test passage as proof of policy effectiveness.
