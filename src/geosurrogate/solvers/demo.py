"""DemoSolver: pool-based oracle over precomputed FEM results.

Every SRF served in demo mode is a real RS2 result loaded from
demo_cases/<case>/lookup.csv. The active-learning loop restricts its
candidates to the unused pool points, so the solver only ever receives
assignments that match a pool row exactly.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..config import ProjectConfig
from .base import CaseResult, MaterialInfo

ENV_DEMO_DIR = "GEOSURROGATE_DEMO_CASES"


class DemoCaseError(RuntimeError):
    pass


def demo_cases_dir() -> Path:
    env = os.environ.get(ENV_DEMO_DIR)
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "demo_cases"


def load_registry() -> dict:
    reg = demo_cases_dir() / "registry.yaml"
    if not reg.exists():
        raise DemoCaseError(f"demo case registry not found: {reg}")
    return yaml.safe_load(reg.read_text(encoding="utf-8"))


def load_case_config(case_id: str) -> ProjectConfig:
    case_yaml = demo_cases_dir() / case_id / "case.yaml"
    if not case_yaml.exists():
        raise DemoCaseError(f"unknown demo case '{case_id}' (missing {case_yaml})")
    return ProjectConfig.from_yaml(case_yaml)


class DemoSolver:
    is_pool_based = True

    def __init__(self, config: ProjectConfig):
        case_id = config.solver.demo_case
        self.case_dir = demo_cases_dir() / case_id
        lookup_path = self.case_dir / "lookup.csv"
        if not lookup_path.exists():
            raise DemoCaseError(f"lookup table not found for demo case '{case_id}': {lookup_path}")
        self.config = config
        self.var_ids = config.var_ids
        self.lookup = pd.read_csv(lookup_path)
        missing = [v for v in self.var_ids if v not in self.lookup.columns]
        if missing:
            raise DemoCaseError(f"lookup.csv lacks variable columns {missing}")
        if "srf" not in self.lookup.columns:
            raise DemoCaseError("lookup.csv lacks 'srf' column")
        self._X = self.lookup[self.var_ids].to_numpy(dtype=float)
        self._used: set[int] = set()
        self._delay = config.solver.simulate_delay_s

    # --- pool management -------------------------------------------------
    def pool(self) -> pd.DataFrame:
        """Unused pool points (index preserved from lookup table)."""
        mask = ~self.lookup.index.isin(self._used)
        return self.lookup.loc[mask, self.var_ids]

    def sync_used(self, X_existing: pd.DataFrame) -> int:
        """Mark pool points already present in a dataset (resume support)."""
        n = 0
        for _, row in X_existing.iterrows():
            idx = self._match(row[self.var_ids].to_numpy(dtype=float))
            if idx is not None:
                self._used.add(idx)
                n += 1
        return n

    def _match(self, x: np.ndarray) -> int | None:
        mask = np.all(np.isclose(self._X, x, rtol=1e-9, atol=1e-12), axis=1)
        for idx in np.flatnonzero(mask):
            if idx not in self._used:
                return int(idx)
        return None

    # --- FEMSolver interface ---------------------------------------------
    def connect(self) -> None:
        pass

    def list_materials(self) -> list[MaterialInfo]:
        names = list(dict.fromkeys(v.material for v in self.config.variables))
        return [MaterialInfo(name=n, index=i) for i, n in enumerate(names)]

    def run_case(self, assignments: dict[str, float], workdir: Path, case_id: str) -> CaseResult:
        x = np.array([assignments[v] for v in self.var_ids], dtype=float)
        idx = self._match(x)
        if idx is None:
            return CaseResult(case_id=case_id, srf=None, status="fem_error", elapsed_s=0.0)
        if self._delay > 0:
            time.sleep(self._delay)
        self._used.add(idx)
        srf = float(self.lookup.loc[idx, "srf"])
        return CaseResult(case_id=case_id, srf=srf, status="ok", elapsed_s=self._delay)

    def shutdown(self) -> None:
        pass
