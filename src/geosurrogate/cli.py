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
