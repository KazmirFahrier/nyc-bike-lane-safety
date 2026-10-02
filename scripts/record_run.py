"""Record source hashes, environment and observed validation outputs."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    receipts = {}
    for path in sorted((ROOT / 'data/raw').glob('*.receipt.json')):
        value = json.loads(path.read_text())
        # Do not store machine specific paths or any environment secrets.
        value.pop('output_path', None)
        receipts[path.name] = value
    unit = ET.parse(ROOT / 'logs/unit_tests.xml').find('testsuite')
    assert unit is not None
    assert int(unit.attrib['failures']) == 0 and int(unit.attrib['errors']) == 0
    results = json.loads((ROOT / 'dbt/target/run_results.json').read_text())['results']
    tests = [r for r in results if r['unique_id'].startswith('test.')]
    assert all(r['status'] == 'pass' for r in tests)
    r = pd.read_csv(ROOT / 'analysis/output/r_validation.csv')
    pg = json.loads((ROOT / 'analysis/output/postgis_validation.json').read_text())
    assert r.delta.max() < 1e-9
    assert all(pg[k] == 0 for k in ['only_python', 'only_postgis', 'python_splits', 'postgis_splits'])
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'data/raw').glob('*.parquet'))}
    code = [p for folder in ['src', 'analysis', 'scripts', 'dbt', 'tests'] for p in (ROOT / folder).rglob('*')
            if p.suffix in ['.py', '.R', '.sql', '.yml', '.sh']
            and not any(x in p.parts for x in ['target', 'dbt_packages', '__pycache__'])]
    code += [ROOT / 'Makefile', ROOT / 'pyproject.toml', ROOT / 'docs/brief/brief_template.md']
    model_outputs = [p for p in (ROOT / 'analysis/output').glob('*.csv')]
    model_outputs += [ROOT / 'docs/brief/protected-bike-lanes-brief.pdf']
    manifest = {
        'recorded_utc': datetime.now(UTC).isoformat(),
        'base_commit': subprocess.check_output(['git','merge-base','HEAD','origin/main'], cwd=ROOT, text=True).strip(),
        'code_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sorted(code)},
        'source_sha256': source_hashes, 'source_receipts': receipts,
        'python': platform.python_version(),
        'packages': {p: importlib.metadata.version(p) for p in ['duckdb','pandas','numpy','pyfixest','statsmodels','geopandas','shapely','dbt-core','dbt-duckdb','weasyprint']},
        'validation': {'python_tests_passed': int(unit.attrib['tests']), 'dbt_data_tests_passed': len(tests),
                       'r_group_time_cells': len(r), 'r_max_absolute_delta': float(r.delta.max()),
                       'postgis': pg},
        'output_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sorted(model_outputs)},
    }
    (ROOT / 'analysis/output/run_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Recorded reconciled sources, versions, hashes and validation results')


if __name__ == '__main__':
    main()
