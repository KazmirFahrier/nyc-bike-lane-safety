#!/usr/bin/env bash
# Fresh checkout, live inputs, full publication, and numerical comparison.
set -euo pipefail
TARGET="${1:-$(mktemp -d "${TMPDIR:-/tmp}/nycbike-cleanroom.XXXXXX")}"
REPO="https://github.com/KazmirFahrier/nyc-bike-lane-safety.git"
REF="${NYCBIKE_REF:-main}"
if [[ -d "$TARGET" && -n "$(ls -A "$TARGET")" ]]; then
  echo "Target must be empty: $TARGET" >&2
  exit 1
fi
git clone --quiet --branch "$REF" "$REPO" "$TARGET"
cd "$TARGET"
mkdir -p work/reference
cp analysis/output/did_summary.csv work/reference/did_summary.csv
cp analysis/output/count_models.csv work/reference/count_models.csv
make setup
make all
.venv/bin/pytest tests/ -q
.venv/bin/python scripts/validate_publication.py
.venv/bin/python - <<'PY'
import numpy as np
import pandas as pd
for filename, columns in [('did_summary.csv', ['att','ci_lo','ci_hi','baseline_rate']),
                          ('count_models.csv', ['coef','se','n'])]:
    reference = pd.read_csv('work/reference/' + filename).set_index('spec').sort_index()
    current = pd.read_csv('analysis/output/' + filename).set_index('spec').sort_index()
    assert reference.index.equals(current.index), filename
    if not np.allclose(reference[columns], current[columns], rtol=1e-8, atol=1e-10, equal_nan=True):
        raise SystemExit('Reproduction differs: ' + filename + '. Inspect source receipts and package versions.')
print('Fresh checkout: model estimates and intervals match the committed publication')
PY
