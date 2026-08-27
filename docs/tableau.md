# Building the Tableau Public dashboard

The interactive dashboard in `docs/dashboard/dashboard.html` is the working version and is
self-contained. This document is for rebuilding it in Tableau Public, which several of the
target postings ask for by name.

**Publishing to Tableau Public requires signing in to a Tableau account**, so that step is
not automated here — the extracts below are shaped so the build is mechanical.

## Extracts

`make dashboard-data` writes these to `data/tableau/`. Each file is one grain, which is what
Tableau wants; joining across grains inside Tableau causes duplicate-row inflation.

| File | Grain | Rows | Use for |
|---|---|---|---|
| `corridors.csv` | one corridor | 2,234 | the corridor table, borough rollups, maps |
| `corridor_year_panel.csv` | corridor × year | 26,808 | anything with a time axis |
| `citywide_by_year.csv` | year | 12 | injuries and ridership trend |
| `equity_by_quintile.csv` | quintile × measure | 10 | lane miles per 10,000 residents |
| `equity_timing.csv` | quintile × measure | 10 | median install year |
| `estimates.csv` | specification | 3 | the headline comparison |

## Key fields

| Field | Type | Notes |
|---|---|---|
| `corridor_id` | string | join key across corridor and panel grains |
| `treatment_cohort` | string | `switcher`, `never_treated`, `always_treated`, `treated_after_window` |
| `first_protected_year` | int | null for never-treated |
| `inj_per_seg_year` | float | **use this, not raw `injuries`** — raw counts confound corridor length with risk |
| `n_segments` | int | corridor length in blocks; the denominator above |
| `income`, `share_poc` | float | length-weighted tract characteristics of the corridor |
| `ridership_index` | float | citywide, 2014 = 100. Not corridor-specific — see caveats |

## Four views, plus a caveats tab

Matching the working dashboard:

1. **Overview** — KPI tiles (corridors, treated, injuries, deaths) and the three-estimate
   comparison from `estimates.csv` as a bar-with-reference-line on zero.
2. **The build-out** — corridors treated per year from `corridors.csv`, plus protected share
   by borough.
3. **Equity** — `equity_by_quintile.csv` and `equity_timing.csv` as paired bars.
4. **Corridors** — `corridors.csv` as a sortable table.
5. **Data caveats** — a text tab. Do not skip it. It is the tab that makes the rest
   trustworthy, and it is the one most portfolio dashboards leave out.

## Two things to get right

**Do not sum `inj_per_seg_year`.** It is already a rate. Aggregate it with a weighted
average — `SUM([injuries]) / SUM([n_segments] * [years])` — or Tableau will report nonsense
at every level above the corridor.

**Do not present any estimate as the effect of a protected lane.** The three specifications
disagree in sign because treatment timing is selected on a transitory injury spike. The
dashboard's framing — "three defensible methods, three different answers" — is the honest
one and should survive the port.
