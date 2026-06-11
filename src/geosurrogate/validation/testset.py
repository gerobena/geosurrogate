"""Independent labeled validation batch for real-solver projects.

Generates an LHS sample inside the training box (the TFM convention for the
massive-validation sets: uniform space-filling coverage, stricter than
distribution-weighted sampling), simulates it with the project's solver and
saves a labeled file ready for `geosurrogate validate --massive --test-xlsx`.

Resumable: partial results are appended to a CSV after every simulation, so
an interrupted batch continues where it stopped.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from .. import doe
from ..project import Project
from ..solvers import get_solver


def generate_testset(project: Project, n: int, seed: int,
                     dry_run: bool = False) -> Path:
    cfg = project.config
    X = doe.lhs(n, cfg.bounds(), seed=seed)
    inputs = pd.DataFrame(X, columns=cfg.var_ids)

    out_dir = project.root / "validation"
    out_dir.mkdir(exist_ok=True)
    tag = f"n{n}_seed{seed}"
    final_path = out_dir / f"testset_{tag}.xlsx"
    partial_path = out_dir / f"testset_{tag}_partial.csv"

    if dry_run:
        preview = out_dir / f"testset_{tag}_inputs.xlsx"
        inputs.to_excel(preview, index=False)
        project.log(f"testset dry-run: {n} LHS inputs written to {preview}")
        return preview

    solver = get_solver(cfg)
    if getattr(solver, "is_pool_based", False):
        raise RuntimeError("demo projects already ship a labeled pool - "
                           "use `validate --use-pool` instead of a testset")

    done = pd.read_csv(partial_path) if partial_path.exists() else pd.DataFrame()
    start = len(done)
    if start:
        project.log(f"testset: resuming, {start}/{n} already simulated")

    solver.connect()
    try:
        for i in range(start, n):
            assignments = {v: float(inputs.iloc[i][v]) for v in cfg.var_ids}
            case_id = f"Test_{i + 1:04d}"
            result = solver.run_case(assignments, project.fem_dir / "testset", case_id)
            row = {**assignments, "srf": result.srf, "status": result.status,
                   "elapsed_s": round(result.elapsed_s, 2)}
            done = pd.concat([done, pd.DataFrame([row])], ignore_index=True)
            tmp = partial_path.with_suffix(".csv.tmp")
            done.to_csv(tmp, index=False)
            os.replace(tmp, partial_path)
            project.append_event("testset_case_done", case_id=case_id,
                                 srf=result.srf, status=result.status,
                                 elapsed_s=round(result.elapsed_s, 2),
                                 message=result.message)
            project.log(f"  {case_id} ({i + 1}/{n}) -> SRF = {result.srf} "
                        f"({result.status})")
            if result.message:
                project.log(f"    failure detail: {result.message}")
    finally:
        solver.shutdown()

    ok = done[done["status"] == "ok"]
    ok[[*cfg.var_ids, "srf"]].to_excel(final_path, index=False)
    project.log(f"testset complete: {len(ok)}/{n} valid FEM results -> {final_path}")
    project.append_event("testset_done", n_requested=n, n_ok=int(len(ok)),
                         file=str(final_path))
    return final_path
