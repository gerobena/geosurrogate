"""Data helpers shared by the validation analyses."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..project import Project


def train_arrays(project: Project) -> tuple[np.ndarray, np.ndarray]:
    ds = project.load_dataset()
    ok = ds[ds["status"] == "ok"]
    if len(ok) < 4:
        raise RuntimeError("not enough simulated points for validation analyses")
    X = ok[project.config.var_ids].to_numpy(dtype=float)
    y = ok["srf"].to_numpy(dtype=float)
    return X, y


def load_test_set(project: Project, test_xlsx: Path | None, use_pool: bool) -> pd.DataFrame:
    """Independent labeled test set: columns = var ids + 'srf'.

    Sources: an Excel/CSV of FEM results (real mode), or — for demo projects —
    the unused part of the precomputed pool (every point is a real RS2 result
    the surrogate has never seen).
    """
    cfg = project.config
    if test_xlsx is not None:
        path = Path(test_xlsx)
        df = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
        missing = [c for c in (*cfg.var_ids, "srf") if c not in df.columns]
        if missing:
            raise ValueError(f"test set lacks columns {missing}; expected variable "
                             f"ids {cfg.var_ids} plus 'srf'")
        return df[[*cfg.var_ids, "srf"]].dropna()
    if use_pool:
        if cfg.solver.type != "demo":
            raise ValueError("--use-pool only applies to demo projects")
        from ..solvers.demo import demo_cases_dir
        lookup = pd.read_csv(demo_cases_dir() / cfg.solver.demo_case / "lookup.csv")
        ds = project.load_dataset()
        used = ds[ds["status"] == "ok"][cfg.var_ids].to_numpy(dtype=float)
        pool_X = lookup[cfg.var_ids].to_numpy(dtype=float)
        is_used = np.zeros(len(lookup), dtype=bool)
        for row in used:
            is_used |= np.all(np.isclose(pool_X, row, rtol=1e-9, atol=1e-12), axis=1)
        return lookup.loc[~is_used, [*cfg.var_ids, "srf"]].reset_index(drop=True)
    raise ValueError("no test set: pass --test-xlsx <file> or, for demo projects, --use-pool")
