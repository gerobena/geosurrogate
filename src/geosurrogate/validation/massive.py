"""Massive validation: surrogate vs an independent set of FEM results.

Single fit on the full training data, prediction over the labeled test set,
accuracy metrics (R2, RMSE) and the two-sample Kolmogorov-Smirnov test on
the SRF distributions. K-S wording follows the rigorous formulation: the
test either rejects or fails to reject H0 — it never "proves equality".
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


def run_massive(project: Project, test_xlsx: Path | None = None,
                use_pool: bool = False) -> dict:
    cfg = project.config
    X, y = train_arrays(project)
    test = load_test_set(project, test_xlsx, use_pool)
    project.log(f"Massive validation: {len(X)} training points vs "
                f"{len(test)} independent FEM results")

    import os
    import shutil
    workdir = project.surrogate_dir / f"work_massive_{os.getpid()}"
    try:
        mean, s2 = fit_predict(
            workdir=workdir,
            X_train=X, y_train=y,
            X_pred=test[cfg.var_ids].to_numpy(dtype=float),
            bounds=cfg.bounds(), surrogate_cfg=cfg.surrogate,
            rscript_path=cfg.solver.rscript_path, timeout_s=cfg.solver.timeout_s,
            log=project.log,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    actual = test["srf"].to_numpy(dtype=float)
    resid = actual - mean
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((actual - actual.mean())**2))
    ks = stats.ks_2samp(actual, mean)
    metrics = {
        "n_train": int(len(X)),
        "n_test": int(len(test)),
        "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        "rmse": float(np.sqrt(ss_res / len(test))),
        "mae": float(np.mean(np.abs(resid))),
        "max_abs_error": float(np.max(np.abs(resid))),
        "ks_D": float(ks.statistic),
        "ks_pvalue": float(ks.pvalue),
        "ks_h0_rejected_at_005": bool(ks.pvalue < 0.05),
    }

    out_dir = project.root / "validation"
    out_dir.mkdir(exist_ok=True)
    out = test[cfg.var_ids].copy()
    out["actual_srf"] = actual
    out["pred_srf"] = mean
    out["pred_s2"] = s2
    out.to_csv(out_dir / "massive.csv", index=False)
    (out_dir / "massive_metrics.json").write_text(json.dumps(metrics, indent=1),
                                                  encoding="utf-8")

    from ..reporting.figures import massive_panel
    fig_path = out_dir / "massive_panel.png"
    massive_panel(actual, mean, metrics, fig_path)
    metrics["figure"] = str(fig_path)
    project.append_event("massive_validation_done",
                         **{k: v for k, v in metrics.items()
                            if isinstance(v, (int, float, bool))})
    return metrics
