# Scope note

*Written D1. Amended as constraints surface — amendments are dated, not overwritten.*

## Question

Did NYC's 2013–2024 protected bike lane build-out reduce cyclist injuries on the
corridors that received lanes, relative to matched untreated corridors, once ridership
exposure is controlled — and were gains distributed evenly across neighborhoods?

## Unit of analysis

Street segment × year. Segments come from the DOT bike route layer's `segmentid`, which
is the NYC LION street centerline identifier, so treated and untreated corridors share a
common spatial key.

## Treatment

A segment is treated in year *t* if an on-street protected facility
(`ft_facilit` or `tf_facilit` = 'Protected' **and** `onoffst` = 'ON') was installed on or
before *t* and had not been retired. 4,357 segments switch within the window.

Excluded from both treatment and control:
- Off-street protected paths (greenways) — different intervention, different exposure.
- Always-treated segments installed before 2013 (1,009) — no observed pre-period.

## Outcome

Count of cyclist injuries per segment-year, from NYPD crash records geocoded to within
100 ft of the segment centerline. Killed and injured modelled separately where counts
permit; KSI (killed or severely injured) is the preferred severity cut if the Person
file supports it.

## Exposure

Ridership proxy from DOT automated counters. **This is the weakest link in the design
and is named as such in the brief:** 41 counter sites cannot directly measure ridership
on 4,357 segments. The counters support a citywide and borough-level ridership index,
not a segment-level one. Segment-level exposure is therefore modelled, not measured, and
the robustness grid (D9) reports how much the headline estimate moves under alternative
exposure assumptions — including no exposure adjustment at all.

## Design

Staggered-adoption difference-in-differences with a negative binomial outcome and a
log-exposure offset. Because treatment timing is staggered, a two-way fixed effects
estimator is biased when effects vary over time; the estimator used will be robust to
this (Callaway–Sant'Anna or an equivalent), and the naive TWFE estimate is reported
alongside it so the difference is visible.

## What this study cannot answer

- Whether lanes caused ridership to rise (reverse causality with exposure).
- Whether unreported injuries changed — NYPD records only crashes that were reported.
- Anything about near-misses, comfort, or perceived safety.
- Whether a *particular* corridor's lane worked. Estimates are averages.

## Amendments

- **2026-08-24 (D1):** Citi Bike System Data (`vsnr-94wk`) is not a tabular Socrata
  dataset — it is a link record pointing at S3 trip files, and returns HTTP 403 to the
  SoDA API. Citi Bike trip data, if used for exposure, must be pulled from
  `s3.amazonaws.com/tripdata/` as monthly CSV archives instead. The project plan listed
  it as a Socrata endpoint; that was wrong.
