"""Shared timing definition for report and dashboard publication."""

from __future__ import annotations

import pandas as pd


def timing_records(corridors: pd.DataFrame) -> list[dict]:
    """Reuse population quintiles; never rerank only the treated subset."""
    treated = corridors[corridors['treatment_cohort'].eq('switcher')]
    records = []
    for key, kind in [('income_q', 'income'), ('poc_q', 'poc')]:
        for label, d in treated.groupby(key, observed=True):
            records.append({'kind': kind, 'quintile': int(str(label)[1]),
                            'median_year': float(d.first_protected_year.median()),
                            'corridors': len(d)})
    return records
