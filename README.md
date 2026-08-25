# Protected Bike Lanes and Cyclist Injuries in New York City

**Did NYC's protected bike lane build-out reduce cyclist injuries, once you account for
the fact that more people started riding on exactly the streets that got the lanes?**

A staggered difference-in-differences study of 4,357 on-street protected bike lane
segments installed between 2013 and 2024, using NYPD crash records, DOT bike route
geometry, DOT automated bicycle counters, and ACS demographics.

> **Status: in progress.** Ingestion and the treatment definition are built and
> reconciled. Models, maps, dashboard, and the policy brief are not finished yet.
> No findings are claimed on this page until they exist. See [Roadmap](#roadmap).

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

## Roadmap

- [x] Project scaffold, config, reconciled Socrata client
- [x] Crash ingestion (57,353 cyclist-involved records, reconciled)
- [x] Treatment ingestion + protected-lane definition
- [ ] Exposure and ACS ingestion, data dictionary
- [ ] PostGIS spatial join: crashes to street corridors
- [ ] dbt staging/intermediate/marts with tests
- [ ] Matched comparison corridors
- [ ] Difference-in-differences + parallel-trends plot
- [ ] Negative binomial with exposure offset + robustness grid
- [ ] Equity stratification by tract
- [ ] Maps, dashboard, six-page policy brief
- [ ] Clean-room reproduction

## License

Code MIT. Data belongs to the City of New York and the Census Bureau under their own terms.
