# Protected Bike Lanes and Cyclist Injuries in New York City

**Did NYC's protected bike lane build-out reduce cyclist injuries, once you account for
the fact that more people started riding on exactly the streets that got the lanes?**

A staggered difference-in-differences study of 4,357 on-street protected bike lane
segments installed between 2013 and 2024, using NYPD crash records, DOT bike route
geometry, DOT automated bicycle counters, and ACS demographics.

> **Status: analysis complete, presentation layer in progress.** Pipeline, models,
> verification and the policy brief are done. Maps, dashboard, and the equity
> stratification are not. See [Roadmap](#roadmap).

> Independent analysis by a private individual, written on my own initiative using public
> data. Not affiliated with, commissioned by, endorsed by, or speaking for the New York City
> Department of Transportation, the Vision Zero program, or any government agency or
> organization. Findings and any errors are my own.

## The finding

**The question cannot be answered with this data, and the reason is the finding.**

NYC DOT installs protected bike lanes where cyclists are already being hurt.
Corridors that received one saw their cyclist-injury rate **rise 55% over the five
years before installation** (0.076 → 0.119 injuries per segment-year) while matched
comparison corridors stayed flat (0.090 → 0.092).

That is well-targeted policy. It also breaks the standard evaluation method, because
a problem that has just spiked tends to subside whether or not you intervene. Three
defensible analytic choices give three answers that do not agree on direction:

| Specification | Estimate | 95% CI |
|---|---|---|
| Callaway–Sant'Anna, base = last pre-year | **−17.7%** | −57% to +20% |
| Callaway–Sant'Anna, base = earlier pre-window | **+8.0%** | −17% to +35% |
| Poisson FE within corridor, CEM-matched | **+12.1%** | −4% to +31% |
| *(naive two-way fixed effects, shown for contrast)* | *+21.2%* | — |

None is statistically distinguishable from zero. The gap between row 1 and rows 2–3
is not a fact about bike lanes — it is a fact about which pre-treatment year you
anchor to, and treated corridors' injuries peak in exactly the year row 1 uses.

**This is not evidence that protected lanes fail.** It is evidence that the
observational record cannot settle the question, and that any published figure which
does not address the targeting problem deserves suspicion — including figures that
flatter the program.

📄 **[Read the six-page policy brief](docs/brief/protected-bike-lanes-brief.pdf)** (PDF) ·
also built as a [web version](docs/brief/brief_web.html)

![Injuries on treated corridors rose 55% before the lane went in](analysis/output/raw_trends.png)

---

## The question, stated precisely

Between 2013 and 2024 the NYC Department of Transportation installed protected bike
lanes on 4,357 street segments. Cyclist injuries citywide rose over the same period.
Both facts are true and neither answers the policy question, because ridership rose
too — and it rose *most* on the corridors that got lanes.

So this study asks three things:

1. **Effect.** On corridors that received a protected lane, did cyclist injuries fall
   relative to matched comparison corridors that did not, in the years after install?
2. **Exposure.** Does that answer survive controlling for ridership? A lane that
   triples riding and doubles injuries has *halved* the risk per rider. Injury counts
   alone cannot distinguish safety from popularity.
3. **Equity.** Were the corridors that got lanes distributed evenly across
   neighborhoods, and did the safety gains land evenly?

## Method

Staggered-adoption difference-in-differences on a segment-by-year panel, with a
negative binomial outcome model carrying a ridership-exposure offset.

**Identifying assumption, stated up front:** absent the lane, injury trends on treated
corridors would have moved parallel to matched control corridors. This is an
assumption, not a finding. The pre-treatment trend plot that tests it is published in
the brief *whatever it shows* — including if it undermines the design.

**Known threat to identification:** DOT does not install lanes at random. Lanes go
where riding is already growing and where crashes are already a known problem, which
biases in opposite directions. Matching on pre-period ridership, crash history, street
class, and borough narrows this; it does not eliminate it. The brief says so.

## Data

| Source | Dataset | Rows | Role |
|---|---|---|---|
| NYPD via NYC Open Data | Motor Vehicle Collisions – Crashes (`h9gi-nx95`) | 57,353 cyclist-involved, 2013–24 | Outcome |
| NYPD via NYC Open Data | Motor Vehicle Collisions – Person (`f55k-p6yu`) | — | Injury severity |
| NYC DOT | Bike Routes (`mzxg-pwib`) | 29,695 segments | Treatment + timing |
| NYC DOT | Bicycle Counts (`uczf-rk3c`) | 7.4M counter readings | Exposure |
| NYC DOT | Bicycle Counters (`smn3-rzf9`) | 41 counter sites | Exposure geography |
| NYC DOT | Bicycle & Pedestrian Counts (`ct66-47at`) | 21.0M | Exposure |
| Census Bureau | ACS 5-Year, tract level | — | Equity stratification |

All sources are public and free. Endpoints verified live 2026-08-24.

### Three data decisions that change the answer

**1. "Protected" means two different things in the DOT file.** 5,220 Current segments
are on-street protected lanes; 3,215 are greenway and park paths, coded identically.
These are not the same intervention — greenways have no adjacent motor traffic and a
different rider population. Only on-street segments are treated. Off-street segments
are excluded from the control pool too, since they are not comparable streets.

**2. 403 "protected" segments carry install dates before 1990** — 1894, 1900, 1909 —
inherited from the underlying street centerline, not from any bike facility. Anything
installed before 2013 is classified always-treated and dropped from the DiD; it can be
neither a clean control nor a clean switcher.

**3. 439 protected segments are Retired.** A corridor that gained a lane and later lost
it is not "treated" for the whole panel. Treatment history is reconstructed per segment
per year from the `prevbikeid` version chain, not assumed from the current snapshot.

### Two things not filtered, on purpose

Ungeocoded crash records are landed, not dropped at ingest. The share of NYPD crash
records missing coordinates changes over time, and silently dropping them would hide a
data-quality problem that belongs in the brief. The loss is quantified in dbt instead.

The study window stops at 2024-12-31. Recent months of crash data are revised upward as
reports are filed, which manufactures a fake downward trend at the right edge of any
time series that runs to today.

## Reproducing

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and Docker (for PostGIS).

```bash
git clone https://github.com/KazmirFahrier/nyc-bike-lane-safety.git
cd nyc-bike-lane-safety
uv venv && uv pip install -e ".[dev]"
cp .env.example .env        # add a free Socrata app token; unauthenticated pulls are throttled
source .venv/bin/activate

python -m nycbike.ingest.crashes
python -m nycbike.ingest.bike_routes
```

Every pull writes a `*.receipt.json` beside its parquet recording the server's own row
count, the rows landed, the exact filter, and the timestamp. A pull whose landed count
does not match the server's count **raises** rather than writing a short file — silent
under-collection is the most common way an analysis ends up quietly wrong.

Row counts drift upward as NYC backfills crash records. The receipts are what make the
clean-room reproduction checkable: same filter, same expected count, or the upstream
data changed and we can say by exactly how much.

## Repository layout

```
src/nycbike/          ingestion, config, Socrata client with reconciliation
  ingest/             one module per source
dbt/                  staging -> intermediate -> marts, with tests
sql/                  PostGIS spatial join
analysis/             DiD, negative binomial, R script
docs/                 data dictionary, scope note, policy brief (Quarto)
tests/                pytest
```

## Verification

Three independent checks, because a result nobody can reproduce is a claim, not a finding.

| Check | Result |
|---|---|
| Estimator implemented twice — Python, and R written from the definition | agree to 1 part in 10¹⁵ across all 99 group-time cells |
| Corridor construction built twice — DuckDB graph components, and PostGIS `ST_ClusterDBSCAN` | **identical partition** of all 20,439 segments |
| dbt test suite | 39 passing, incl. end-to-end injury conservation |
| Every data pull | reconciled against the source's own `count(*)`; a short pull raises rather than writing |
| **Clean-room reproduction** — fresh clone, live data re-pulled, `bash scripts/clean_room.sh` | **all five key figures match exactly** |

The clean-room run earned its place: it caught three build failures invisible on the
development machine — a circular Python/dbt dependency that only worked because the
database already existed, a missing `dbt deps`, and a `staging+` selector that pulled in
descendants when it needed ancestors. Each would have met the first person to clone the repo.

## Roadmap

- [x] Scaffold, config, reconciled Socrata client
- [x] Crash ingestion (57,353 cyclist-involved records)
- [x] Treatment ingestion + protected-lane definition
- [x] Exposure ingestion + chained ridership index; generated data dictionary
- [x] Spatial join with tie-breaking and contested-assignment flagging
- [x] dbt staging → intermediate → marts, 39 tests
- [x] Corridor aggregation, verified against PostGIS
- [x] Cohort-specific coarsened exact matching
- [x] Callaway–Sant'Anna DiD + event study + base-period sensitivity
- [x] Poisson FE specification ladder; R cross-validation
- [x] Six-page policy brief
- [x] Clean-room reproduction from a fresh clone
- [ ] Equity stratification by tract *(blocked: needs a free Census API key)*
- [ ] QGIS maps and Tableau Public dashboard

## License

Code MIT. Data belongs to the City of New York and the Census Bureau under their own terms.
