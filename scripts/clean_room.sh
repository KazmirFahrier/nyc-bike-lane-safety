#!/usr/bin/env bash
# Clean-room reproduction: clone the repo somewhere else, build it from nothing,
# and check the numbers that appear in the brief come back.
#
# This is the check that catches what you have stopped noticing about your own
# machine -- a package installed by hand, a file that only exists locally, a
# path that happens to resolve. It runs with a small bootstrap because it is
# testing that the pipeline reproduces, not reproducing the confidence intervals.
#
# Usage:  bash scripts/clean_room.sh [target-dir]
set -euo pipefail

TARGET="${1:-/tmp/nycbike-cleanroom}"
REPO="https://github.com/KazmirFahrier/nyc-bike-lane-safety.git"

echo "=== clean-room reproduction into $TARGET ==="
rm -rf "$TARGET"
git clone --quiet "$REPO" "$TARGET"
cd "$TARGET"

echo "--- setup ---"
uv venv --quiet
uv pip install --quiet -e ".[dev]"
uv pip install --quiet pyfixest

echo "--- ingest (re-pulls from the live APIs) ---"
.venv/bin/python -m nycbike.ingest.crashes
.venv/bin/python -m nycbike.ingest.bike_routes
.venv/bin/python -m nycbike.ingest.exposure

echo "--- spatial join and corridors ---"
.venv/bin/python -m nycbike.spatial_join
.venv/bin/python -m nycbike.corridors

echo "--- dbt build (all tests must pass) ---"
cd dbt && DBT_PROFILES_DIR=. ../.venv/bin/dbt build && cd ..

echo "--- analysis ---"
NYCBIKE_N_BOOT=50 .venv/bin/python analysis/did.py
.venv/bin/python analysis/count_models.py

echo ""
echo "=== KEY FIGURES: clean room vs the brief ==="
.venv/bin/python - <<'PY'
import duckdb, numpy as np, pandas as pd
con = duckdb.connect("data/nycbike.duckdb", read_only=True)
q = lambda s: con.execute(s).fetchone()

checks = [
  ("corridors in panel",        q("select count(distinct corridor_id) from main.fct_corridor_year_panel")[0], 2234),
  ("switcher corridors",        q("select count(distinct corridor_id) from main.fct_corridor_year_panel where treatment_cohort='switcher'")[0], 519),
  ("never-treated corridors",   q("select count(distinct corridor_id) from main.fct_corridor_year_panel where treatment_cohort='never_treated'")[0], 1573),
  ("treated corridors matched", q("select count(*) from main.int_matched_corridors where is_treated_here and in_common_support")[0], 472),
]
print(f"{'figure':<28}{'clean room':>12}{'brief':>10}  ")
ok = True
for name, got, want in checks:
    flag = "match" if got == want else f"DIFFERS by {got-want:+d}"
    if got != want: ok = False
    print(f"{name:<28}{got:>12,}{want:>10,}  {flag}")

cm = pd.read_csv("analysis/output/count_models.csv")
pct = 100*(np.exp(cm.loc[cm.spec=='4_poisson_fe_matched','coef'].iloc[0])-1)
print(f"{'Poisson FE matched effect':<28}{pct:>11.1f}%{12.1:>9.1f}%  "
      f"{'match' if abs(pct-12.1)<0.5 else 'DIFFERS'}")
print()
print("NOTE: upstream row counts drift as NYC backfills crash records, so small")
print("      differences are expected and are visible in the pull receipts.")
print("REPRODUCTION:", "CLEAN" if ok else "DIFFERENCES FOUND -- see above")
PY
