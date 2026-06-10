"""Typed project configuration (single source of truth: project.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_VERSION = 1


class Distribution(BaseModel):
    family: Literal["normal", "lognormal", "triangular", "uniform"]
    mean: float | None = None
    std: float | None = None
    low: float | None = None
    high: float | None = None
    mode: float | None = None
    truncate: tuple[float, float] | None = None

    @model_validator(mode="after")
    def _check_family_params(self) -> "Distribution":
        if self.family in ("normal", "lognormal"):
            if self.mean is None or self.std is None:
                raise ValueError(f"{self.family} distribution requires mean and std")
            if self.std <= 0:
                raise ValueError("std must be > 0")
            if self.family == "lognormal" and self.mean <= 0:
                raise ValueError("lognormal mean must be > 0")
        elif self.family == "uniform":
            if self.low is None or self.high is None:
                raise ValueError("uniform distribution requires low and high")
            if not self.low < self.high:
                raise ValueError("uniform requires low < high")
        elif self.family == "triangular":
            if self.low is None or self.high is None or self.mode is None:
                raise ValueError("triangular distribution requires low, mode and high")
            if not self.low <= self.mode <= self.high or self.low >= self.high:
                raise ValueError("triangular requires low <= mode <= high and low < high")
        if self.truncate is not None and not self.truncate[0] < self.truncate[1]:
            raise ValueError("truncate must be (low, high) with low < high")
        return self

    def central_value(self) -> float:
        """Representative central value (used e.g. for smoke-test simulations)."""
        if self.family in ("normal", "lognormal"):
            return float(self.mean)
        if self.family == "uniform":
            return (self.low + self.high) / 2
        return float(self.mode)


class VariableSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    material: str
    property: Literal["cohesion", "friction_angle"]
    training_bounds: tuple[float, float]
    distribution: Distribution

    @field_validator("training_bounds")
    @classmethod
    def _ordered(cls, v: tuple[float, float]) -> tuple[float, float]:
        if not v[0] < v[1]:
            raise ValueError("training_bounds must be (low, high) with low < high")
        return v


class PortsConfig(BaseModel):
    modeler: int = 60054
    interpreter: int = 60055


class SolverConfig(BaseModel):
    type: Literal["rs2", "demo"]
    model_file: Path | None = None
    demo_case: str | None = None
    rscript_path: Path = Path(r"C:\Program Files\R\R-4.5.3\bin\Rscript.exe")
    # RS2 location: by default RS2Scripting auto-detects the most recent RS2
    # installation via the Windows registry. These overrides are only needed
    # on machines with non-standard installs or multiple RS2 versions.
    rs2_modeler_executable: Path | None = None
    rs2_interpreter_executable: Path | None = None
    ports: PortsConfig = PortsConfig()
    timeout_s: int = Field(default=1800, gt=0)
    fem_retention: Literal["keep_all", "keep_failed", "keep_none"] = "keep_all"
    simulate_delay_s: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _check_target(self) -> "SolverConfig":
        if self.type == "demo" and not self.demo_case:
            raise ValueError("solver.type=demo requires solver.demo_case")
        if self.type == "rs2" and self.model_file is None:
            raise ValueError("solver.type=rs2 requires solver.model_file")
        return self


class DoEConfig(BaseModel):
    strategy: Literal["lhs", "lhs_maximin", "pem", "hybrid_lhs_pem", "factorial_3"] = "hybrid_lhs_pem"
    n_lhs: int = Field(default=40, ge=0)
    n_pem: int = Field(default=40, ge=0)
    seed: int = 42

    @model_validator(mode="after")
    def _check_total(self) -> "DoEConfig":
        if self.strategy == "factorial_3":
            return self  # design size is 3^D, resolved at design time from the variable count
        total = self.n_lhs if self.strategy in ("lhs", "lhs_maximin") else (
            self.n_pem if self.strategy == "pem" else self.n_lhs + self.n_pem)
        if total < 3:
            raise ValueError("initial design needs at least 3 points")
        return self


class ValidationGridConfig(BaseModel):
    n: int = Field(default=10000, gt=0)
    seed: int = 999


class ALConfig(BaseModel):
    acquisition: Literal["alc"] = "alc"
    tolerance: float = Field(default=0.01, gt=0)
    max_iterations: int = Field(default=50, gt=0)
    budget_total_sims: int = Field(default=120, gt=0)
    n_candidates: int = Field(default=1000, gt=0)
    refresh_candidates: bool = True
    validation_grid: ValidationGridConfig = ValidationGridConfig()
    seed: int = 123


class MCMCConfig(BaseModel):
    nmcmc: int = Field(default=3000, gt=0)
    burn: int = Field(default=1000, ge=0)
    thin: int = Field(default=2, gt=0)

    @model_validator(mode="after")
    def _check_burn(self) -> "MCMCConfig":
        if self.burn >= self.nmcmc:
            raise ValueError("burn must be < nmcmc")
        return self


class SurrogateConfig(BaseModel):
    engine: Literal["deepgp_r"] = "deepgp_r"
    mcmc: MCMCConfig = MCMCConfig()
    kernel: Literal["exp2", "matern"] = "exp2"
    separable: bool = True
    seed: int = 123


class ExploitationConfig(BaseModel):
    mcs_samples: int = Field(default=100_000, gt=0)
    failure_threshold: float = Field(default=1.0, gt=0)
    seed: int = 7


class ProjectMeta(BaseModel):
    name: str
    schema_version: int = SCHEMA_VERSION


class ProjectConfig(BaseModel):
    project: ProjectMeta
    solver: SolverConfig
    variables: list[VariableSpec] = Field(min_length=1)
    doe: DoEConfig = DoEConfig()
    active_learning: ALConfig = ALConfig()
    surrogate: SurrogateConfig = SurrogateConfig()
    exploitation: ExploitationConfig = ExploitationConfig()

    @model_validator(mode="after")
    def _unique_ids(self) -> "ProjectConfig":
        ids = [v.id for v in self.variables]
        if len(set(ids)) != len(ids):
            raise ValueError("variable ids must be unique")
        return self

    @property
    def dims(self) -> int:
        return len(self.variables)

    @property
    def var_ids(self) -> list[str]:
        return [v.id for v in self.variables]

    def bounds(self) -> list[tuple[float, float]]:
        return [v.training_bounds for v in self.variables]

    @classmethod
    def from_yaml(cls, path: Path | str) -> "ProjectConfig":
        with open(path, encoding="utf-8") as f:
            return cls.model_validate(yaml.safe_load(f))

    def to_yaml(self, path: Path | str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.model_dump(mode="json"), f, sort_keys=False, allow_unicode=True)
