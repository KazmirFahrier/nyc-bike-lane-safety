"""Treatment removal and missing citywide exposure must not invent treatment."""

import numpy as np
import pandas as pd
from count_models import prepare_panel


def test_count_panel_uses_recorded_status_and_retains_2013():
    d = pd.DataFrame({"n_segments": [1, 1, 1], "panel_year": [2013, 2020, 2021],
                      "is_treated": [False, False, True],
                      "first_protected_year": [2018, 2018, 2018],
                      "has_undated_removal": [False, False, True],
                      "log_segments": [0.0, 0.0, 0.0],
                      "log_exposure": [np.nan, 1.0, 1.0]})
    out = prepare_panel(d)
    assert out.panel_year.tolist() == [2013, 2020]
    assert out.treated_now.tolist() == [0, 0]
    assert out.offset_term.tolist() == [0, 0]
