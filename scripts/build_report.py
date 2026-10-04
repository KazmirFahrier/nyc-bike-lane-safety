"""Generate report numbers and narrative from the same model outputs."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template

import duckdb
import pandas as pd

from nycbike.equity_summary import timing_records

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    payload = json.loads((ROOT / 'docs/dashboard/data.json').read_text())
    summary = pd.read_csv(ROOT / 'analysis/output/did_summary.csv')
    if summary.n_boot.min() < 1000:
        raise ValueError('Publication requires at least 1000 bootstrap draws; smoke output is not publishable')
    con = duckdb.connect(str(ROOT / 'data/nycbike.duckdb'), read_only=True)
    counts = con.execute('''select treatment_cohort, count(distinct corridor_id)
        from main.fct_corridor_year_panel group by 1''').fetchall()
    counts = dict(counts)
    tests = json.loads((ROOT / 'dbt/target/run_results.json').read_text())['results']
    data_tests = [r for r in tests if r['unique_id'].startswith('test.')]
    if not data_tests or any(r['status'] != 'pass' for r in data_tests):
        raise ValueError('Run dbt build or test successfully before generating the report')
    rows = ['| Specification | Change relative to baseline | 95% interval |',
            '|---|---:|---:|']
    labels = ['Staggered adoption, last preyear', 'Staggered adoption, earlier four years',
              'Poisson FE, unweighted common support sample']
    for label, r in zip(labels, payload['estimates'], strict=True):
        rows.append(f"| {label} | {r['pct']:+.1f}% | {r['lo']:+.1f}% to {r['hi']:+.1f}% |")
    table = '\n'.join(rows)
    cor = pd.read_csv(ROOT / 'analysis/output/equity_corridors.csv')
    timing_rows = ['| Corridor demographic group | Median installation year | Corridors |',
                   '|---|---:|---:|']
    for r in timing_records(cor):
        group = 'Income' if r['kind'] == 'income' else 'POC share'
        timing_rows.append(f"| {group}, Q{r['quintile']} | {r['median_year']:g} | {r['corridors']} |")
    equity = pd.DataFrame(payload['equity'])
    income = equity[equity.kind.eq('income')].set_index('quintile')
    values = {
        'report_date': 'October 1, 2026',
        'corridors': f"{payload['meta']['corridors']:,}",
        'switchers': f"{counts['switcher']:,}",
        'matched': str(int(summary.matched_treated_corridors.iloc[0])),
        'estimates': table,
        'timing_table': '\n'.join(timing_rows),
        'rich_miles': f"{income.loc[5, 'miles_per_10k']:.2f}",
        'middle_miles': f"{income.loc[3, 'miles_per_10k']:.2f}",
        'poor_miles': f"{income.loc[1, 'miles_per_10k']:.2f}",
        'growth': f"{payload['meta']['ridership_growth_pct']:.1f}",
        'data_tests': str(len(data_tests)),
    }
    template = (ROOT / 'docs/brief/brief_template.md').read_text()
    (ROOT / 'docs/brief/brief.md').write_text(Template(template).substitute(values))
    result = (f"The corrected panel contains **{values['corridors']} corridors**, including "
              f"**{values['switchers']}** first treated during 2013 through 2024. "
              f"The matched absorbing design includes **{values['matched']} treated corridors**, "
              "with complete baseline windows and dated treatment histories.\n\n" + table + '\n\n'
              'The staggered adoption intervals include zero. The common support Poisson interval '
              'is above zero, but neither design establishes a credible causal safety effect. '
              'These are injury count estimates, not risk per cyclist.\n')
    (ROOT / 'docs/current_results.md').write_text('# Current results\n\n' + result)
    readme = (ROOT / 'README.md').read_text()
    start, end = '<!-- RESULTS_START -->', '<!-- RESULTS_END -->'
    before, rest = readme.split(start, 1)
    _, after = rest.split(end, 1)
    (ROOT / 'README.md').write_text(before + start + '\n' + result + end + after)
    # Keep the landing page typography while rebuilding its content from results.
    page = ROOT / 'docs/index.html'
    head = page.read_text().split('<body>', 1)[0]
    html_rows = ''.join(f"<tr><td>{label}</td><td>{r['pct']:+.1f}%</td>"
                        f"<td>{r['lo']:+.1f}% to {r['hi']:+.1f}%</td></tr>"
                        for label, r in zip(labels, payload['estimates'], strict=True))
    body = f'''<body><main class="wrap">
<p class="eyebrow">Independent analysis of NYC public data</p>
<h1>Protected bike lanes and cyclist injuries in New York City</h1>
<p class="stand">What the observational record can tell us, and the assumptions it cannot resolve.</p>
<div class="byline"><strong>Kazmir Fahrier</strong><span>Corrected {values['report_date']}</span>
<span>{values['corridors']} corridors, 57,353 crash records, 2013 through 2024</span></div>
<div class="cards">
<a class="card" href="dashboard/dashboard.html"><span class="card__k">Interactive</span><span class="card__t">Protected Lane Tracker</span><span class="card__d">Injuries, infrastructure, equity and data limitations.</span></a>
<a class="card" href="brief/brief_web.html"><span class="card__k">Analysis</span><span class="card__t">Read the policy brief</span><span class="card__d">Methods, results and interpretation.</span></a>
<a class="card" href="brief/protected-bike-lanes-brief.pdf"><span class="card__k">PDF</span><span class="card__t">Download the brief</span><span class="card__d">The same report in print format.</span></a>
</div>
<h2>The corrected results</h2>
<table><thead><tr><th>Specification</th><th>Estimate</th><th>95% interval</th></tr></thead><tbody>{html_rows}</tbody></table>
<div class="finding"><p>The staggered adoption intervals include zero. The common support Poisson interval is above zero.
These specifications do not establish a credible causal safety effect. They do not measure injury risk per rider.</p></div>
<p>Matching uses borough and prior injury counts. The standard staggered adoption design excludes known removals and undated retirements, and includes {values['matched']} treated corridors with complete baseline windows.</p>
<h2>Observed provision and timing</h2>
<p>Protected mileage ever recorded per 10,000 residents is {values['rich_miles']} in the richest tract quintile and {values['middle_miles']} in the middle quintile. These are neighborhood comparisons, not measurements of who uses a lane.</p>
<figure><img src="assets/equity.png" alt="Recorded protected lane mileage by tract demographic quintile"></figure>
<p>Timing groups use quintiles defined over all corridors with observed demographics before restricting to treated corridors. The brief and dashboard use the same groups and preserve fractional medians.</p>
<h2>What changed and why</h2>
<p>The correction preserves annual lane removals, separates different treatment histories, repairs matching support and baseline windows, removes an ineffective ridership offset, aligns equity groupings, and regenerates the analysis and reports together.</p>
<p><a href="https://github.com/KazmirFahrier/nyc-bike-lane-safety/blob/main/docs/corrections.md">Correction details and validation</a> · <a href="https://github.com/KazmirFahrier/nyc-bike-lane-safety">Code and reproduction instructions</a></p>
<footer><p>Independent analysis of public data. Not affiliated with or endorsed by NYC DOT or any government agency. Findings and errors are my own.</p></footer>
</main></body></html>'''
    page.write_text(head + body)
    con.close()
    print('Updated README results, landing page and both report sources')


if __name__ == '__main__':
    main()
