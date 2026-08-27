# Spatial layers and GIS

## What the maps are

The three maps in `analysis/output/` are produced by `analysis/maps.py` using GeoPandas
and matplotlib, and they regenerate with the pipeline. That is a deliberate choice: a map
exported by hand from a desktop GIS drifts from the numbers the moment the data updates,
and cannot be reproduced by a reviewer.

- `map_buildout.png` — where protected lanes went in, and when
- `map_injuries.png` — cyclist injuries per segment-year by corridor, quantile-classed
- `map_equity.png` — protected lanes over tract median household income

All are drawn in **EPSG:2263** (NAD83 / New York Long Island, US survey feet), the city's
own projection. Distances are in feet, and shapes are not distorted the way a Web Mercator
basemap distorts them at this latitude.

**No QGIS project file is shipped.** QGIS is not installed in the environment this was
built in, so a `.qgs` written here could not be opened and verified. Shipping an untested
project file that might fail to load would be worse than shipping none. The layers below
open cleanly in QGIS, ArcGIS Pro, or anything else that reads GeoPackage.

## Layers

| File | Layer | Geometry | CRS | Contents |
|---|---|---|---|---|
| `data/raw/bike_routes.gpkg` | `bike_routes` | MultiLineString | EPSG:4326 | All 29,695 DOT bike route segments, with `is_treated_facility`, `is_protected`, `is_onstreet`, `instdate` |
| `data/external/acs_tracts.gpkg` | `tracts` | MultiPolygon | EPSG:4326 | 2,327 NYC census tracts with ACS income, race, poverty and derived shares |
| `data/interim/segment_corridors.parquet` | — | — | — | Segment → corridor mapping, joins to `bike_routes` on `segmentid` |

To reproduce the corridor layer in PostGIS instead:

```bash
make postgis-up && make postgis-corridors
```

That builds corridors with `ST_ClusterDBSCAN` and verifies the partition against the
DuckDB build segment for segment. See `sql/postgis/02_corridors.sql` for why
`ST_LineMerge` was the wrong tool.

## Styling used in the maps

Reproduce these in QGIS to get the same look:

**Build-out** — graduated on `instdate` year, 5 classes (2013–15, 2016–17, 2018–19,
2020–21, 2022–24), blues ramp `#9ecae1 → #08306b`, width 1.9. Non-protected routes as a
single light grey `#c9cfd6` line, width 0.35, drawn beneath.

**Injuries** — graduated on injuries per segment-year, **quantile** classes at the 50th,
75th, 90th and 97th percentiles, oranges ramp `#dfe3e8 → #a63603`, width scaled 0.6→3.0.
Quantile rather than equal interval: the distribution is heavily right-skewed and equal
intervals put roughly 90% of corridors in the lowest class.

**Equity** — tracts graduated on `median_household_income`, Greens, stretched between the
2nd and 98th percentiles so a handful of very high-income tracts do not flatten the ramp.
Protected lanes over the top in `#7f2704`, width 1.6.
