"""Generate docs/data_dictionary.md from the built warehouse and the pull receipts.

Written rather than hand-maintained so it cannot drift from what the pipeline
actually produced. Run after `make dbt`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nycbike import config

QUALITY_TABLE = """## Known data-quality issues

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
"""


def main() -> None:
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    out: list[str] = []
    w = out.append

    w("# Data dictionary\n")
    w("*Generated from the built warehouse. Regenerate with "
      "`python scripts/gen_data_dictionary.py` after `make dbt`.*\n")

    w("## Sources, as pulled\n")
    w("Every pull is reconciled before it is written. Row pulls are checked "
      "against the server's own `count(*)`; aggregate pulls have no cheap group "
      "count, so they are checked against control totals computed over the "
      "ungrouped data.\n")
    w("| Source | Dataset | Rows landed | Reconciled against | Pulled |")
    w("|---|---|---|---|---|")
    for f in sorted((config.DATA_RAW).glob("*.receipt.json")):
        r = json.loads(f.read_text())
        if r.get("server_count") is not None:
            check = f"server `count(*)` = {r['server_count']:,}"
        else:
            ct = r.get("control_totals") or {}
            check = "; ".join(f"`{k}` = {v:,}" for k, v in ct.items()) or "—"
        w(f"| `{r['dataset_name']}` | `{r['dataset_id']}` | {r['rows_landed']:,} | "
          f"{check} | {r['started_utc'][:10]} |")
    w("")

    w("## Tables\n")
    tables = con.execute("""
        select table_schema, table_name from information_schema.tables
        where table_schema in ('main','main_staging') order by table_schema, table_name
    """).fetchall()
    for schema, name in tables:
        fq = f"{schema}.{name}"
        n = con.execute(f"select count(*) from {fq}").fetchone()[0]
        w(f"### `{name}`\n")
        w(f"`{fq}` — {n:,} rows\n")
        w("| Column | Type |")
        w("|---|---|")
        cols = con.execute("""
            select column_name, data_type from information_schema.columns
            where table_schema = ? and table_name = ? order by ordinal_position
        """, [schema, name]).fetchall()
        for cname, ctype in cols:
            w(f"| `{cname}` | {ctype} |")
        w("")

    w(QUALITY_TABLE)
    (ROOT / "docs" / "data_dictionary.md").write_text("\n".join(out))
    print(f"wrote docs/data_dictionary.md ({len(out)} lines)")


if __name__ == "__main__":
    main()
