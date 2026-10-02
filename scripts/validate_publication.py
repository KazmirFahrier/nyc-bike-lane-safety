"""Verify that displayed estimates and timing agree with estimator outputs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from nycbike.equity_summary import timing_records

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    data = json.loads((ROOT / 'docs/dashboard/data.json').read_text())
    did = pd.read_csv(ROOT / 'analysis/output/did_summary.csv').set_index('spec')
    cm = pd.read_csv(ROOT / 'analysis/output/count_models.csv').set_index('spec')
    for i, spec in enumerate(['cs_did_base_last_pre_year', 'cs_did_base_early_window']):
        r = did.loc[spec]
        expected = [round(100 * r[c] / r.baseline_rate, 1) for c in ['att', 'ci_lo', 'ci_hi']]
        assert expected == [data['estimates'][i][c] for c in ['pct', 'lo', 'hi']]
    r = cm.loc['4_poisson_fe_matched']
    expected = [round(100 * (np.exp(x) - 1), 1) for x in
                [r.coef, r.coef - 1.96 * r.se, r.coef + 1.96 * r.se]]
    assert expected == [data['estimates'][2][c] for c in ['pct', 'lo', 'hi']]
    equity = pd.read_csv(ROOT / 'analysis/output/equity_corridors.csv')
    assert data['timing'] == timing_records(equity)
    html = (ROOT / 'docs/dashboard/dashboard.html').read_text()
    assert json.dumps(data, separators=(',', ':')) in html
    for file in ['README.md', 'docs/brief/brief.md', 'docs/brief/brief_web.html', 'docs/index.html']:
        text = (ROOT / file).read_text()
        for estimate in data['estimates']:
            assert f"{estimate['pct']:+.1f}%" in text, (file, estimate)
        assert '55%' not in text and 'one part in a quadrillion' not in text
    print('Publication estimates, baseline, timing groups and inlined data agree')


if __name__ == '__main__':
    main()
