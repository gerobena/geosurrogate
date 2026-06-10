"""Solver adapter interface: every FEM backend (RS2, demo, future PLAXIS/FLAC) implements this."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

CaseStatus = Literal["ok", "fem_error", "no_convergence", "timeout"]


@dataclass
class MaterialInfo:
    name: str
    index: int
    criterion: str = "mohr_coulomb"
    current_values: dict[str, float] = field(default_factory=dict)


@dataclass
class CaseResult:
    case_id: str
    srf: float | None
    status: CaseStatus
    elapsed_s: float
    fem_file: Path | None = None
    message: str | None = None  # failure detail for diagnostics


@runtime_checkable
class FEMSolver(Protocol):
    """Contract consumed by the active-learning loop.

    `assignments` maps variable id (from ProjectConfig.variables) to a value;
    the adapter resolves material + property internally.
    """

    is_pool_based: bool

    def connect(self) -> None: ...

    def list_materials(self) -> list[MaterialInfo]: ...

    def run_case(self, assignments: dict[str, float], workdir: Path, case_id: str) -> CaseResult: ...

    def shutdown(self) -> None: ...
