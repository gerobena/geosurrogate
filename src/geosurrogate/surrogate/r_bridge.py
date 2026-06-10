"""Python <-> R contract: one clean call that fits the GP, predicts and scores ALC.

Scaling policy (single source, unlike the TFM scripts where it was duplicated
per R script): X is scaled to [0,1]^D using the *training bounds* from the
config (stable across iterations), y is standardized with the current training
mean/sd. R receives scaled data and returns scaled predictions; this module
de-standardizes before handing results back.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import SurrogateConfig
from ..doe import to_unit

R_SCRIPT = Path(__file__).resolve().parent / "r" / "fit_predict_alc.R"


class RBridgeError(RuntimeError):
    pass


class RScriptNotFound(RBridgeError):
    pass


@dataclass
class SurrogateResult:
    mean_cand: np.ndarray
    s2_cand: np.ndarray
    alc: np.ndarray
    mean_valid: np.ndarray
    s2_valid: np.ndarray
    diagnostics: dict = field(default_factory=dict)


def fit_predict_alc(
    workdir: Path,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_cand: np.ndarray,
    X_valid: np.ndarray,
    bounds: list[tuple[float, float]],
    surrogate_cfg: SurrogateConfig,
    rscript_path: Path,
    timeout_s: int,
    log=print,
    do_alc: bool = True,
) -> SurrogateResult:
    rscript_path = Path(rscript_path)
    if not rscript_path.exists():
        raise RScriptNotFound(
            f"Rscript not found at '{rscript_path}'. Install R (>= 4.x) with the "
            f"'deepgp' package, or fix solver.rscript_path in project.yaml."
        )
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    d = len(bounds)
    xcols = [f"x{i + 1}" for i in range(d)]

    y_mean = float(np.mean(y_train))
    y_sd = float(np.std(y_train, ddof=1))
    if not np.isfinite(y_sd) or y_sd < 1e-12:
        y_sd = 1.0

    df_train = pd.DataFrame(to_unit(X_train, bounds), columns=xcols)
    df_train["y"] = (np.asarray(y_train, dtype=float) - y_mean) / y_sd
    df_train.to_csv(workdir / "train.csv", index=False)

    df_pred = pd.DataFrame(np.vstack([to_unit(X_cand, bounds), to_unit(X_valid, bounds)]), columns=xcols)
    df_pred["set"] = ["cand"] * len(X_cand) + ["valid"] * len(X_valid)
    df_pred.to_csv(workdir / "predict.csv", index=False)

    mcmc = surrogate_cfg.mcmc
    cmd = [
        str(rscript_path), str(R_SCRIPT), str(workdir),
        str(mcmc.nmcmc), str(mcmc.burn), str(mcmc.thin),
        str(surrogate_cfg.seed), surrogate_cfg.kernel,
        "1" if surrogate_cfg.separable else "0", "1" if do_alc else "0",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        raise RBridgeError(f"R worker exceeded timeout of {timeout_s}s") from e
    for stream, content in (("stdout", proc.stdout), ("stderr", proc.stderr)):
        content = (content or "").strip()
        if content:
            log(f"[R {stream}] {content}")
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-8:]
        raise RBridgeError("R worker failed (exit %d):\n%s" % (proc.returncode, "\n".join(tail)))

    preds = pd.read_csv(workdir / "predictions.csv")
    if do_alc:
        alc = pd.read_csv(workdir / "alc.csv")["alc"].to_numpy(dtype=float)
    else:
        alc = np.empty(0)
    n_cand = len(X_cand)
    mean_all = preds["mean"].to_numpy(dtype=float) * y_sd + y_mean
    s2_all = preds["s2"].to_numpy(dtype=float) * y_sd**2

    diagnostics = {}
    diag_path = workdir / "diagnostics.json"
    if diag_path.exists():
        diagnostics = json.loads(diag_path.read_text(encoding="utf-8"))

    return SurrogateResult(
        mean_cand=mean_all[:n_cand],
        s2_cand=s2_all[:n_cand],
        alc=alc,
        mean_valid=mean_all[n_cand:],
        s2_valid=s2_all[n_cand:],
        diagnostics=diagnostics,
    )


def fit_predict(
    workdir: Path,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_pred: np.ndarray,
    bounds: list[tuple[float, float]],
    surrogate_cfg: SurrogateConfig,
    rscript_path: Path,
    timeout_s: int,
    log=print,
) -> tuple[np.ndarray, np.ndarray]:
    """Prediction-only path (validation/exploitation): fit the GP on the
    training data and predict mean/s2 on X_pred. No ALC, no validation grid."""
    res = fit_predict_alc(
        workdir=workdir, X_train=X_train, y_train=y_train,
        X_cand=X_pred, X_valid=np.empty((0, len(bounds))),
        bounds=bounds, surrogate_cfg=surrogate_cfg,
        rscript_path=rscript_path, timeout_s=timeout_s, log=log, do_alc=False,
    )
    return res.mean_cand, res.s2_cand
