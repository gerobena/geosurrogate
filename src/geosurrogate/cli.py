"""Command-line interface.

  geosurrogate demo list
  geosurrogate demo run slope_2d [--fast] [--budget N] [--workdir DIR] [--delay S]
  geosurrogate run <project_dir>
  geosurrogate ui
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import typer

from .config import ProjectConfig
from .project import Project

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help="Active-learning GP surrogates for geotechnical FEM reliability analysis.")
demo_app = typer.Typer(no_args_is_help=True, help="Run packaged demo cases (no FEM license needed).")
app.add_typer(demo_app, name="demo")


def _run_project(project: Project) -> None:
    from .activelearning import loop

    reason = loop.run(project)
    state = project.read_state()
    typer.echo("-" * 60)
    typer.echo(f"Run finished: {reason}")
    typer.echo(f"  simulations (ok): {state.get('n_samples')} / budget {state.get('budget_total')}")
    if state.get("error_max") is not None:
        typer.echo(f"  last surface error_max: {state['error_max']:.5f}")
    typer.echo(f"  dataset: {project.dataset_path}")
    typer.echo(f"  events : {project.events_path}")


@demo_app.command("list")
def demo_list() -> None:
    """List available demo cases."""
    from .solvers.demo import load_registry

    reg = load_registry()
    for case_id, meta in (reg.get("cases") or {}).items():
        typer.echo(f"  {case_id:<16} {meta.get('dims')}D  {meta.get('title')}  "
                   f"[pool: {meta.get('points')} FEM results]")
    for case_id, meta in (reg.get("planned") or {}).items():
        typer.echo(f"  {case_id:<16} (planned) {meta.get('note')}")


@demo_app.command("run")
def demo_run(
    case_id: str = typer.Argument(..., help="Demo case id, e.g. slope_2d"),
    workdir: Path = typer.Option(None, help="Project folder to create (default: runs/<case>_<ts>)"),
    budget: int = typer.Option(None, help="Override total FEM budget"),
    fast: bool = typer.Option(False, "--fast", help="Lighter MCMC and validation grid (quick check)"),
    delay: float = typer.Option(None, help="Simulated seconds per FEM case (demo realism)"),
) -> None:
    """Create a project from a demo case and run the full loop on real precomputed FEM results."""
    from .solvers.demo import load_case_config

    cfg = load_case_config(case_id)
    data = cfg.model_dump(mode="json")
    if budget is not None:
        data["active_learning"]["budget_total_sims"] = budget
    if delay is not None:
        data["solver"]["simulate_delay_s"] = delay
    if fast:
        data["surrogate"]["mcmc"] = {"nmcmc": 1000, "burn": 300, "thin": 2}
        data["active_learning"]["validation_grid"]["n"] = min(
            1500, data["active_learning"]["validation_grid"]["n"])
    cfg = ProjectConfig.model_validate(data)

    if workdir is None:
        workdir = Path("runs") / f"{case_id}_{dt.datetime.now():%Y%m%d_%H%M%S}"
    project = Project.create(workdir, cfg)
    typer.echo(f"Project created at {workdir}")
    _run_project(project)


@app.command("new")
def new_cmd(
    config_file: Path = typer.Argument(..., help="Project config YAML (real-solver or demo)"),
    workdir: Path = typer.Option(None, "--workdir", "-w", help="Project folder to create"),
) -> None:
    """Create a project folder from a config YAML file."""
    import yaml

    raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    model_file = (raw.get("solver") or {}).get("model_file")
    if model_file:
        p = Path(model_file)
        if not p.is_absolute():
            p = (config_file.parent / p).resolve()
        raw["solver"]["model_file"] = str(p)
    cfg = ProjectConfig.model_validate(raw)
    if workdir is None:
        workdir = Path("runs") / f"{config_file.stem}_{dt.datetime.now():%Y%m%d_%H%M%S}"
    Project.create(workdir, cfg)
    typer.echo(f"Project created at {workdir}")
    typer.echo(f"Preflight: geosurrogate check {workdir} [--simulate]")
    typer.echo(f"Run:       geosurrogate run {workdir}")


@app.command("check")
def check_cmd(
    project_dir: Path = typer.Argument(..., help="Existing project folder"),
    simulate: bool = typer.Option(False, "--simulate",
                                  help="Run ONE smoke simulation at central values and time it"),
) -> None:
    """Preflight: connect to the solver, list model materials against the
    configured variables, and optionally run a single timed smoke simulation."""
    from .solvers import get_solver

    project = Project.open(project_dir)
    cfg = project.config
    typer.echo(f"Solver: {cfg.solver.type} | model: {cfg.solver.model_file}")
    solver = get_solver(cfg)
    typer.echo("Connecting...")
    solver.connect()
    try:
        mats = solver.list_materials()
        typer.echo(f"Materials in model ({len(mats)}):")
        for m in mats:
            cur = ", ".join(f"{k}={v:g}" for k, v in m.current_values.items()) or "-"
            typer.echo(f"  [{m.index}] {m.name}  ({m.criterion})  {cur}")
        names = {m.name for m in mats}
        missing = [v for v in cfg.variables if v.material not in names]
        for v in missing:
            typer.echo(f"  WARNING: variable '{v.id}' references material "
                       f"'{v.material}' which is not in the model")
        if not missing:
            typer.echo("All configured variables map to model materials: OK")
        if simulate:
            if getattr(solver, "is_pool_based", False):
                typer.echo("--simulate applies to real solvers only (demo serves "
                           "precomputed points); skipping.")
                return
            assignments = {v.id: v.distribution.central_value() for v in cfg.variables}
            pretty = ", ".join(f"{k}={v:g}" for k, v in assignments.items())
            typer.echo(f"Smoke simulation at central values: {pretty}")
            res = solver.run_case(assignments, project.fem_dir / "smoke", "Case_smoke")
            typer.echo(f"  -> SRF = {res.srf} ({res.status}) in {res.elapsed_s:.0f} s")
            if res.status != "ok":
                if res.message:
                    typer.echo(f"  detail: {res.message}")
                raise typer.Exit(code=1)
    finally:
        solver.shutdown()


@app.command("run")
def run_cmd(project_dir: Path = typer.Argument(..., help="Existing project folder")) -> None:
    """Run (or resume) an existing project."""
    _run_project(Project.open(project_dir))


@app.command("ui")
def ui_cmd() -> None:
    """Launch the dashboard (phase F2)."""
    typer.echo("The Streamlit dashboard arrives in phase F2 (see ARQUITECTURA.md).")


if __name__ == "__main__":
    app()
