"""Active-learning loop: DOE -> (fit GP -> ALC -> FEM -> append -> converge?) -> done.

State machine notes:
- The dataset (dataset.csv) is the source of truth; every phase derives its
  position from it, which makes the loop resumable after any interruption.
- Convergence follows the TFM criterion: max absolute change of the predicted
  surface on a fixed validation grid between consecutive iterations, checked
  BEFORE adding the new point.
- In pool-based mode (demo) the candidate set is the unused pool, so every
  selected point has a real FEM result behind it.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import doe
from ..config import ProjectConfig
from ..project import Project
from ..solvers import get_solver
from ..surrogate import RBridgeError, fit_predict_alc

MAX_CONSECUTIVE_FAILURES = 3


def _ok_rows(ds: pd.DataFrame) -> pd.DataFrame:
    return ds[ds["status"] == "ok"]


def _assignments(var_ids: list[str], x: np.ndarray) -> dict[str, float]:
    return {v: float(val) for v, val in zip(var_ids, x)}


class _Stop(Exception):
    def __init__(self, reason: str):
        self.reason = reason


def run(project: Project) -> str:
    cfg = project.config
    solver = get_solver(cfg)
    solver.connect()
    project.clear_control()
    project.write_state(status="running")
    try:
        if solver.is_pool_based:
            ds = project.load_dataset()
            if len(ds) > 0:
                solver.sync_used(ds[cfg.var_ids])
        _phase_doe(project, solver)
        reason = _phase_al(project, solver)
        status = "paused" if reason == "paused" else "finished"
        project.write_state(phase="done" if status == "finished" else "active_learning",
                            status=status, stop_reason=reason)
        project.append_event("run_finished", reason=reason)
        project.export_xlsx()
        return reason
    except RBridgeError as e:
        project.log(f"ERROR in R worker: {e}")
        project.write_state(status="error", stop_reason="r_error")
        project.append_event("run_error", error=str(e))
        raise
    finally:
        solver.shutdown()


def _check_pause_and_budget(project: Project, n_ok: int) -> None:
    if project.pause_requested():
        raise _Stop("paused")
    if n_ok >= project.config.active_learning.budget_total_sims:
        raise _Stop("budget_exhausted")


def _phase_doe(project: Project, solver) -> None:
    cfg = project.config
    ds = project.load_dataset()
    target = cfg.doe.total
    if len(ds) >= target:
        return
    project.write_state(phase="doe")
    project.append_event("phase_change", phase="doe", target=target, done=len(ds))
    project.log(f"DOE phase: {target} points, {len(ds)} already simulated")

    X_design, labels = doe.design(cfg.doe.strategy, cfg.doe.n_lhs, cfg.doe.n_pem,
                                  cfg.bounds(), cfg.doe.seed)
    remaining = X_design[len(ds):]
    rem_labels = labels[len(ds):]

    if solver.is_pool_based:
        pool = solver.pool()
        idx = doe.select_from_pool(remaining, pool[cfg.var_ids].to_numpy(dtype=float), cfg.bounds())
        remaining = pool.iloc[idx][cfg.var_ids].to_numpy(dtype=float)

    failures = 0
    for x, label in zip(remaining, rem_labels):
        ds = project.load_dataset()
        try:
            _check_pause_and_budget(project, len(_ok_rows(ds)))
        except _Stop as s:
            raise s
        case_id = f"Case_{len(ds) + 1:04d}"
        result = solver.run_case(_assignments(cfg.var_ids, x), project.fem_dir, case_id)
        project.append_case({
            "case_id": case_id, **_assignments(cfg.var_ids, x),
            "srf": result.srf, "predicted_srf": None, "status": result.status,
            "source": f"doe_{label}", "elapsed_s": round(result.elapsed_s, 2),
        })
        project.append_event("doe_case_done", case_id=case_id, srf=result.srf,
                             status=result.status, elapsed_s=round(result.elapsed_s, 2))
        project.log(f"  {case_id} [{label}] -> SRF = {result.srf} ({result.status})")
        if result.status != "ok":
            failures += 1
            if failures >= MAX_CONSECUTIVE_FAILURES:
                raise _Stop("too_many_failures")
        else:
            failures = 0
        n_ok = len(_ok_rows(project.load_dataset()))
        project.write_state(n_samples=n_ok, budget_used=n_ok)


def _phase_al(project: Project, solver) -> str:
    cfg = project.config
    al = cfg.active_learning
    bounds = cfg.bounds()
    valid_prev_path = project.surrogate_dir / "valid_prev.csv"
    X_valid = doe.lhs(al.validation_grid.n, bounds, seed=al.validation_grid.seed)

    project.write_state(phase="active_learning")
    project.append_event("phase_change", phase="active_learning")
    it = int(project.read_state().get("iteration", 0))
    failures = 0

    try:
        while True:
            ds = project.load_dataset()
            ok = _ok_rows(ds)
            _check_pause_and_budget(project, len(ok))
            if it >= al.max_iterations:
                return "max_iterations"

            X_train = ok[cfg.var_ids].to_numpy(dtype=float)
            y_train = ok["srf"].to_numpy(dtype=float)

            if solver.is_pool_based:
                pool = solver.pool()
                if len(pool) == 0:
                    return "pool_exhausted"
                X_cand = pool[cfg.var_ids].to_numpy(dtype=float)
            else:
                cand_seed = al.seed + it if al.refresh_candidates else al.seed
                X_cand = doe.lhs(al.n_candidates, bounds, seed=cand_seed, optimize=True)

            project.log(f"AL iteration {it + 1}: fitting GP on {len(X_train)} points, "
                        f"{len(X_cand)} candidates")
            res = fit_predict_alc(
                workdir=project.surrogate_dir / "work",
                X_train=X_train, y_train=y_train, X_cand=X_cand, X_valid=X_valid,
                bounds=bounds, surrogate_cfg=cfg.surrogate,
                rscript_path=cfg.solver.rscript_path, timeout_s=cfg.solver.timeout_s,
                log=project.log,
            )

            # The stability check is only meaningful between surfaces trained on
            # different data; after a crash-resume the saved surface may come from
            # this very same training set (and an identical MCMC seed), which would
            # yield a trivial delta of 0. The sidecar records the training size.
            error_max = None
            meta_path = valid_prev_path.with_suffix(".json")
            if valid_prev_path.exists() and meta_path.exists():
                prev_n = json.loads(meta_path.read_text(encoding="utf-8")).get("n_train")
                if prev_n is not None and prev_n < len(X_train):
                    prev = pd.read_csv(valid_prev_path)["mean"].to_numpy(dtype=float)
                    error_max = float(np.max(np.abs(res.mean_valid - prev)))
            pd.DataFrame({"mean": res.mean_valid}).to_csv(valid_prev_path, index=False)
            meta_path.write_text(json.dumps({"n_train": len(X_train)}), encoding="utf-8")

            it += 1
            r_diag = {f"r_{k}": v for k, v in res.diagnostics.items() if k != "n_train"}
            project.append_event("al_iteration", iteration=it, n_train=len(X_train),
                                 error_max=error_max, **r_diag)
            project.write_state(iteration=it, error_max=error_max)
            if error_max is not None:
                project.log(f"  surface stability: max |delta| = {error_max:.5f} "
                            f"(tolerance {al.tolerance})")
                if error_max < al.tolerance:
                    return "converged"

            best = int(np.argmax(res.alc))
            x_next = X_cand[best]
            predicted = float(res.mean_cand[best])
            ds = project.load_dataset()
            case_id = f"Case_{len(ds) + 1:04d}"
            result = solver.run_case(_assignments(cfg.var_ids, x_next), project.fem_dir, case_id)
            project.append_case({
                "case_id": case_id, **_assignments(cfg.var_ids, x_next),
                "srf": result.srf, "predicted_srf": round(predicted, 4),
                "status": result.status, "source": "al",
                "elapsed_s": round(result.elapsed_s, 2),
            })
            project.append_event("al_case_done", case_id=case_id, srf=result.srf,
                                 predicted_srf=round(predicted, 4), status=result.status)
            project.log(f"  {case_id} [al] -> SRF = {result.srf} (predicted {predicted:.3f})")
            if result.status != "ok":
                failures += 1
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    return "too_many_failures"
            else:
                failures = 0
            n_ok = len(_ok_rows(project.load_dataset()))
            project.write_state(n_samples=n_ok, budget_used=n_ok)
    except _Stop as s:
        return s.reason
