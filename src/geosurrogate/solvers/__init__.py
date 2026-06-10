"""Solver adapters. RS2 (real mode) lands in F4; demo mode is available from F1."""

from __future__ import annotations

from ..config import ProjectConfig
from .base import CaseResult, FEMSolver, MaterialInfo
from .demo import DemoSolver

__all__ = ["CaseResult", "FEMSolver", "MaterialInfo", "DemoSolver", "get_solver"]


def get_solver(config: ProjectConfig) -> FEMSolver:
    if config.solver.type == "demo":
        return DemoSolver(config)
    if config.solver.type == "rs2":
        from .rs2 import RS2Solver  # lazy: requires the optional RS2Scripting package
        return RS2Solver(config)
    raise ValueError(f"unknown solver type: {config.solver.type}")
