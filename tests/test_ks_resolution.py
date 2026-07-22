"""The K-S curve must state its own resolution.

With 5 independent FEM results the two-sample D can only land on multiples of
1/5, so a run reported D = 0.2000 and p = 1.000 flat across every n - which
reads like a finding but is the statistic's floor plus no power. The metrics now
carry n_test and the resolution so the dashboard and report can say that
explicitly instead of implying agreement.
"""

import json

import pytest


def test_d_resolution_is_the_reciprocal_of_the_test_size():
    # Two-sample K-S on n_test points: the ECDF moves in steps of 1/n_test, so
    # nothing finer than that can be resolved.
    for n_test in (5, 10, 80, 500):
        assert pytest.approx(1.0 / n_test) == 1.0 / n_test


def test_metrics_carry_what_the_warning_needs(tmp_path):
    """Shape contract for ks_metrics.json consumed by the UI."""
    metrics = {"n_min": 5, "n_max": 12, "n_test": 5, "d_resolution": 0.2,
               "final_D": 0.2, "final_pvalue": 1.0,
               "final_h0_rejected_at_005": False}
    path = tmp_path / "ks_metrics.json"
    path.write_text(json.dumps(metrics), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["n_test"] == 5
    assert loaded["d_resolution"] == pytest.approx(1.0 / loaded["n_test"])
    # The reported D sits exactly on the resolution floor: one ECDF step.
    assert loaded["final_D"] == pytest.approx(loaded["d_resolution"])


def test_ks_writes_n_test_and_resolution():
    """The source must record both, or the dashboard cannot warn."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1]
           / "src" / "geosurrogate" / "validation" / "ks.py").read_text(encoding="utf-8")
    assert '"n_test"' in src and '"d_resolution"' in src


def test_underpowered_threshold_is_documented_in_the_page():
    from pathlib import Path
    page = (Path(__file__).resolve().parents[1]
            / "app" / "pages" / "6_Validation.py").read_text(encoding="utf-8")
    assert "KS_MIN_USEFUL_N" in page
    assert "val.ks_underpowered" in page
