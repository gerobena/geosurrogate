"""Distributional convergence curve (two-sample Kolmogorov-Smirnov vs n).

Retrains the surrogate with an increasing number of training simulations
(in their chronological order, which mirrors the active-learning history)
and tracks D and the p-value against an independent labeled test set —
the TFM's signature convergence analysis. D measures the distributional
discrepancy directly (sample-size independent); the p-value depends on the
test's power, so convergence is argued primarily with D.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from ..project import Project
from ..surrogate import fit_predict
from .data import load_test_set, train_arrays


def run_ks_curve(project: Project, test_xlsx: Path | None = None,
                 use_pool: bool = False, n_min: int = 5) -> dict:
    cfg = project.config
    X, y = train_arrays(project)
    test = load_test_set(project, test_xlsx, use_pool)
    X_test = test[cfg.var_ids].to_numpy(dtype=float)
    actual = test["srf"].to_numpy(dtype=float)

    n_total = len(X)
    n_min = max(4, min(n_min, n_total))
    project.log(f"K-S convergence: refitting for n = {n_min}..{n_total} "
                f"against {len(test)} FEM results")

    rows = []
    for n in range(n_min, n_total + 1):
        mean, _ = fit_predict(
            workdir=project.surrogate_dir / "work_ks",
            X_train=X[:n], y_train=y[:n], X_pred=X_test,
            bounds=cfg.bounds(), surrogate_cfg=cfg.surrogate,
            rscript_path=cfg.solver.rscript_path, timeout_s=cfg.solver.timeout_s,
            log=lambda _msg: None,
        )
        ks = stats.ks_2samp(actual, mean)
        rows.append({"n_train": n, "ks_D": float(ks.statistic),
                     "ks_pvalue": float(ks.pvalue)})
        project.log(f"  n={n}: D={ks.statistic:.4f}  p={ks.pvalue:.4f}")

    curve = pd.DataFrame(rows)
    out_dir = project.root / "validation"
    out_dir.mkdir(exist_ok=True)
    curve.to_csv(out_dir / "ks_curve.csv", index=False)

    final = rows[-1]
    metrics = {"n_min": n_min, "n_max": n_total,
               "final_D": final["ks_D"], "final_pvalue": final["ks_pvalue"],
               "final_h0_rejected_at_005": final["ks_pvalue"] < 0.05}
    (out_dir / "ks_metrics.json").write_text(json.dumps(metrics, indent=1),
                                             encoding="utf-8")

    from ..reporting.figures import ks_curve_panel
    fig_path = out_dir / "ks_curve.png"
    ks_curve_panel(curve, fig_path,
                   title=f"{cfg.dims}D Surrogate - Distributional Convergence "
                         f"(two-sample K-S)")
    metrics["figure"] = str(fig_path)
    project.append_event("ks_curve_done", **{k: v for k, v in metrics.items()
                                             if isinstance(v, (int, float, bool))})
    return metrics
