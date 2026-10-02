# Protected bike lanes and cyclist injuries in New York City

An independent analysis of recorded cyclist injuries, bike infrastructure and neighborhood provision from 2013 through 2024. It combines Python, SQL, dbt, DuckDB, PostGIS, R and public NYC and Census data.

[Interactive dashboard and policy brief](https://kazmirfahrier.github.io/nyc-bike-lane-safety/)

Independent analysis by Kazmir Fahrier. Not affiliated with, commissioned by, or endorsed by NYC DOT or any government agency. Findings and errors are my own.

## Current results

<!-- RESULTS_START -->
The corrected panel contains **2,244 corridors**, including **523** first treated during 2013 through 2024. The matched absorbing design includes **383 treated corridors**, with complete baseline windows and dated treatment histories.

| Specification | Change relative to baseline | 95% interval |
|---|---:|---:|
| Staggered adoption, last preyear | -30.6% | -80.1% to +10.1% |
| Staggered adoption, earlier four years | -4.2% | -27.6% to +19.7% |
| Poisson FE, unweighted common support sample | +21.3% | +2.0% to +44.3% |

The staggered adoption intervals include zero. The common support Poisson interval is above zero, but neither design establishes a credible causal safety effect. These are injury count estimates, not risk per cyclist.
<!-- RESULTS_END -->

The original sign reversal narrative has been withdrawn. This analysis does not establish why DOT selected a corridor, whether protected lanes cause harm, or whether they improve safety per cyclist. Local ridership is unobserved.

## October 2026 correction

[What changed, why it mattered and how it was verified](docs/corrections.md)

The correction preserves annual lane removals, separates different treatment histories, repairs support and weighting as controls become treated, uses complete baseline windows, removes a redundant citywide exposure offset, aligns equity groupings and regenerates the full publication together.

The correction record compares old and current estimates and identifies remaining limits. [Current scope](docs/scope.md) describes the implemented design.

## Method

The primary analysis uses staggered adoption group and time comparisons on an absorbing treatment sample. Matching uses borough and injury counts in the three years before installation. Cohorts begin in 2018 to give both baseline specifications complete observations. Never treated and not yet treated controls are eligible; support and control weights are recalculated at each comparison year. Inference uses 1,000 corridor block bootstrap draws with a fixed seed and pointwise intervals.

The count models use annual recorded treatment, exclude undated removals and report corridor and year fixed effects Poisson associations. The common support specification is an unweighted sample restriction, not a collapse of different cohort weights. A pooled negative binomial association and unweighted TWFE comparison are supplementary.

The citywide counter index is descriptive. It is absorbed by year effects and cannot adjust different ridership growth on treated streets. These models estimate recorded injury counts, not risk per rider.

## Data and equity

Live pulls on October 1, 2026 reconciled:

| Source | Study window quantity | Role |
|---|---:|---|
| NYPD Motor Vehicle Collisions | 57,353 cyclist injury or fatality crashes | Outcomes |
| NYC DOT Bike Routes | 29,695 route records | Geometry and treatment |
| NYC DOT Bicycle Counts | 6,208,848 readings; 159,183,214 passages | Descriptive counter index |
| NYC DOT Bicycle Counters | 41 site records | Counter geography |
| Census ACS 2018 through 2022 and TIGER | 2,327 NYC tract records | Neighborhood descriptions |

Every source pull reconciles row counts or aggregate control totals. Source hashes and receipts are recorded in [the run manifest](analysis/output/run_manifest.json). Raw data are downloaded separately and are not committed.

Provision quintiles use tracts with observed demographics. Timing quintiles use all corridors with observed demographics before restricting to treated corridors. Fractional medians are retained. Mileage describes facilities ever recorded as protected, including later removals; it does not measure the current network or the demographics of riders.

## Reproduction

Requires Python 3.11 or later and uv. PDF rendering also requires Pandoc and WeasyPrint system libraries, such as Pango. Docker is required only for the independent PostGIS check; R with data.table, MASS and ggplot2 is required for the R check.

```bash
git clone https://github.com/KazmirFahrier/nyc-bike-lane-safety.git
cd nyc-bike-lane-safety
make setup
make all
.venv/bin/pytest tests/ -q
make postgis-up postgis-corridors
Rscript analysis/did_validation.R
```

A free Socrata app token can be placed in `.env` to reduce throttling; it is optional. Census ingestion uses public summary files and needs no API key.

The main build includes both the staggered adoption estimator and count models. It also regenerates figures, the dashboard, the landing page, the web brief and PDF. The report builder refuses bootstrap smoke outputs with fewer than 1,000 draws. PDF and web content are generated from [one report template](docs/brief/brief_template.md).

Run `bash scripts/clean_room.sh` for a fresh checkout reproduction. Upstream backfills can change results; receipts distinguish source changes from computational differences.

## Validation and limits

CI checks lint, Python unit tests and dbt parsing. The local correction run additionally rebuilt the warehouse from live sources, ran all data tests and compared independent implementations. The correction note gives exact results and separates numerical verification from causal identification.

The design still depends on parallel trends, reconstructed annual treatment dates, reported and geocoded injuries, incomplete counter coverage and ecological demographics. Installation year effects combine untreated and treated months. Event time averages can contain different cohorts. Poisson separation changes its sample. Passing tests does not validate these assumptions.

## Repository

`src/nycbike/` contains ingestion and spatial construction. `dbt/` builds and tests the warehouse. `analysis/` estimates models and produces figures. `scripts/` builds the publications. `docs/` contains scope, corrections, the dashboard and brief. `tests/` exercises known computational failure modes.

## License

Code MIT. Data remain under the terms of the City of New York and Census Bureau.
