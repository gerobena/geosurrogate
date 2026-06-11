"""Leave-One-Out Cross-Validation of the surrogate.

True LOOCV with full refits (MCMC), as in the TFM: for each of the n training
points, the GP is retrained on the remaining n-1 and predicts the held-out
point. Cost: n R fits — use the mcmc override for a quick pass.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil

import numpy as np
import pandas as pd

from ..project import Project
from ..surrogate import fit_predict
from .data import train_arrays


def run_loocv(project: Project) -> dict:
    cfg = project.config
    X, y = train_arrays(project)
    n = len(X)
    project.log(f"LOOCV: {n} refits (one per training point)")

    out_dir = project.root / "validation"
    out_dir.mkdir(exist_ok=True)
    progress_path = out_dir / "loocv_progress.json"
    # per-process workdir: concurrent analyses must never share R scratch files
    workdir = project.surrogate_dir / f"work_loocv_{os.getpid()}"

    preds = np.empty(n)
    variances = np.empty(n)
    try:
        for i in range(n):
            mask = np.arange(n) != i
            mean, s2 = fit_predict(
                workdir=workdir,
                X_train=X[mask], y_train=y[mask], X_pred=X[i:i + 1],
                bounds=cfg.bounds(), surrogate_cfg=cfg.surrogate,
                rscript_path=cfg.solver.rscript_path, timeout_s=cfg.solver.timeout_s,
                log=lambda _msg: None,
            )
            preds[i], variances[i] = mean[0], s2[0]
            project.log(f"  point {i + 1}/{n}: actual={y[i]:.3f} pred={preds[i]:.3f}")
            progress_path.write_text(json.dumps(
                {"done": i + 1, "total": n,
                 "ts": dt.datetime.now().isoformat(timespec="seconds")}),
                encoding="utf-8")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        progress_path.unlink(missing_ok=True)

    resid = y - preds
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((y - y.mean())**2))
    sd = np.sqrt(np.maximum(variances, 0))
    covered = np.abs(resid) <= 2 * sd
    metrics = {
        "n": n,
        "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        "rmse": float(np.sqrt(ss_res / n)),
        "mae": float(np.mean(np.abs(resid))),
        "max_abs_error": float(np.max(np.abs(resid))),
        "coverage_2sd": float(np.mean(covered)),
    }

    pd.DataFrame({"actual_srf": y, "pred_srf": preds, "pred_s2": variances,
                  "residual": resid}).to_csv(out_dir / "loocv.csv", index=False)
    (out_dir / "loocv_metrics.json").write_text(json.dumps(metrics, indent=1),
                                                encoding="utf-8")

    from ..reporting.figures import loocv_panel
    fig_path = out_dir / "loocv_panel.png"
    loocv_panel(y, preds, sd, metrics, fig_path)
    metrics["figure"] = str(fig_path)
    project.append_event("loocv_done", **{k: v for k, v in metrics.items()
                                          if isinstance(v, (int, float))})
    return metrics
