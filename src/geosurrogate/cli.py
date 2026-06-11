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


def _apply_fast(project: Project, fast: bool) -> None:
    if fast:
        data = project.config.model_dump(mode="json")
        data["surrogate"]["mcmc"] = {"nmcmc": 1000, "burn": 300, "thin": 2}
        project.config = ProjectConfig.model_validate(data)
        typer.echo("(fast mode: reduced MCMC - use full mode for reportable metrics)")


@app.command("validate")
def validate_cmd(
    project_dir: Path = typer.Argument(..., help="Existing project folder"),
    loocv: bool = typer.Option(True, "--loocv/--no-loocv",
                               help="Leave-One-Out Cross-Validation (n refits)"),
    massive: bool = typer.Option(False, "--massive",
                                 help="Validation against an independent labeled set"),
    ks: bool = typer.Option(False, "--ks",
                            help="K-S convergence curve vs n (many refits)"),
    test_xlsx: Path = typer.Option(None, "--test-xlsx",
                                   help="Labeled FEM results (columns: var ids + srf)"),
    use_pool: bool = typer.Option(False, "--use-pool",
                                  help="Demo projects: use the unused pool as test set"),
    ks_min: int = typer.Option(5, "--ks-min", help="Starting n for the K-S curve"),
    fast: bool = typer.Option(False, "--fast", help="Reduced MCMC (quick check)"),
) -> None:
    """Validate the trained surrogate of a project (figures + metrics into
    <project>/validation/)."""
    from .validation import run_ks_curve, run_loocv, run_massive

    project = Project.open(project_dir)
    _apply_fast(project, fast)
    if loocv:
        m = run_loocv(project)
        typer.echo(f"LOOCV: R2 = {m['r2']:.4f} | RMSE = {m['rmse']:.4f} | "
                   f"coverage +/-2sd = {100 * m['coverage_2sd']:.0f}%")
    if massive or ks:
        if massive:
            m = run_massive(project, test_xlsx=test_xlsx, use_pool=use_pool)
            verdict = ("H0 rejected" if m["ks_h0_rejected_at_005"]
                       else "H0 not rejected") + " at alpha = 0.05"
            typer.echo(f"Massive: R2 = {m['r2']:.4f} | RMSE = {m['rmse']:.4f} | "
                       f"K-S D = {m['ks_D']:.4f} (p = {m['ks_pvalue']:.3f}; {verdict})")
        if ks:
            m = run_ks_curve(project, test_xlsx=test_xlsx, use_pool=use_pool,
                             n_min=ks_min)
            typer.echo(f"K-S curve: final D = {m['final_D']:.4f} "
                       f"(p = {m['final_pvalue']:.3f})")
    typer.echo(f"Outputs in {project.root / 'validation'}")


@app.command("testset")
def testset_cmd(
    project_dir: Path = typer.Argument(..., help="Existing project folder"),
    n: int = typer.Option(80, "--n", help="Number of independent LHS simulations"),
    seed: int = typer.Option(777, "--seed", help="LHS seed (distinct from training seeds)"),
    dry_run: bool = typer.Option(False, "--dry-run",
                                 help="Write the input design only, without simulating"),
) -> None:
    """Generate an independent labeled validation batch with the real solver
    (LHS inside the training box). Output is ready for
    `geosurrogate validate --massive --ks --test-xlsx <file>`. Resumable."""
    from .validation.testset import generate_testset

    project = Project.open(project_dir)
    path = generate_testset(project, n=n, seed=seed, dry_run=dry_run)
    typer.echo(f"Output: {path}")
    if not dry_run:
        typer.echo(f"Next: geosurrogate validate {project_dir} --no-loocv "
                   f"--massive --ks --test-xlsx {path}")


@app.command("exploit")
def exploit_cmd(
    project_dir: Path = typer.Argument(..., help="Existing project folder"),
    samples: int = typer.Option(None, "--samples",
                                help="MCS sample size (default: config mcs_samples)"),
    fast: bool = typer.Option(False, "--fast", help="Reduced MCMC (quick check)"),
) -> None:
    """Monte Carlo exploitation: SRF distribution and probability of failure
    (figure + metrics into <project>/exploitation/)."""
    from .exploitation import run_mcs

    project = Project.open(project_dir)
    _apply_fast(project, fast)
    m = run_mcs(project, n_samples=samples)
    note = f" ({m['pof_note']})" if m.get("pof_note") else ""
    typer.echo(f"MCS n = {m['n_samples']:,}: SRF mean = {m['srf_mean']:.3f} "
               f"std = {m['srf_std']:.3f}")
    typer.echo(f"PoF = P[SRF < {m['failure_threshold']:g}] = {m['pof']:.4g} "
               f"95% CI [{m['pof_ci95'][0]:.4g}, {m['pof_ci95'][1]:.4g}]{note}")
    typer.echo(f"Outputs in {project.root / 'exploitation'}")


@app.command("report")
def report_cmd(project_dir: Path = typer.Argument(..., help="Existing project folder")) -> None:
    """Generate a self-contained HTML report with all available results."""
    from .reporting.report import generate_report

    path = generate_report(Project.open(project_dir))
    typer.echo(f"Report: {path}")


@app.command("ui")
def ui_cmd(port: int = typer.Option(8501, help="Dashboard port")) -> None:
    """Launch the Streamlit dashboard."""
    import subprocess
    import sys

    app_path = Path(__file__).resolve().parents[2] / "app" / "Home.py"
    if not app_path.exists():
        typer.echo(f"Dashboard entrypoint not found: {app_path}")
        raise typer.Exit(code=1)
    raise SystemExit(subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(app_path),
         "--server.port", str(port)]))


if __name__ == "__main__":
    app()
