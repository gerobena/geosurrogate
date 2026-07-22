"""Testset batch control: honour n, be stoppable, and give up on a broken RS2.

All three come from one real run: the user asked for n=5 and got 80, could not
call the batch off (killing the RS2 window only aborted one simulation - the
next one started), and a failing solver would have burned through every
remaining case.
"""

import json

import pandas as pd
import pytest

from geosurrogate.activelearning import runner
from geosurrogate.config import ProjectConfig
from geosurrogate.project import Project
from geosurrogate.solvers.base import CaseResult
from geosurrogate.validation import testset as ts


@pytest.fixture
def project(tmp_path):
    cfg = ProjectConfig.model_validate({
        "project": {"name": "t"},
        "solver": {"type": "rs2", "model_file": str(tmp_path / "m.fez")},
        "variables": [
            {"id": "c", "material": "m1", "property": "cohesion",
             "training_bounds": [1.0, 2.0],
             "distribution": {"family": "normal", "mean": 1.5, "std": 0.1}},
        ],
    })
    (tmp_path / "m.fez").write_text("stub")
    return Project.create(tmp_path / "proj", cfg)


class FakeSolver:
    """Counts simulations and can be told to fail."""
    is_pool_based = False

    def __init__(self, results=None):
        self.results = results or []
        self.calls = 0
        self.shutdown_calls = 0

    def connect(self):
        pass

    def shutdown(self):
        self.shutdown_calls += 1

    def run_case(self, assignments, workdir, case_id):
        self.calls += 1
        status = (self.results.pop(0) if self.results else "ok")
        return CaseResult(case_id=case_id, srf=(1.0 if status == "ok" else None),
                          status=status, elapsed_s=0.1)


def _patch_solver(monkeypatch, solver):
    monkeypatch.setattr(ts, "get_solver", lambda cfg: solver)


def test_runs_exactly_the_requested_n(monkeypatch, project):
    solver = FakeSolver()
    _patch_solver(monkeypatch, solver)
    ts.generate_testset(project, n=5, seed=777)
    assert solver.calls == 5, "the batch must honour the requested n"
    partial = project.root / "validation" / "testset_n5_seed777_partial.csv"
    assert len(pd.read_csv(partial)) == 5


def test_stop_request_halts_the_batch(monkeypatch, project):
    solver = FakeSolver()
    _patch_solver(monkeypatch, solver)
    # Ask it to stop as soon as the second case would start.
    real_run = solver.run_case

    def run_then_ask_stop(assignments, workdir, case_id):
        result = real_run(assignments, workdir, case_id)
        runner.request_stop(project.root)
        return result

    solver.run_case = run_then_ask_stop
    ts.generate_testset(project, n=20, seed=777)
    assert solver.calls == 1, "must stop at the next case boundary, not run all 20"
    assert solver.shutdown_calls == 1, "RS2 must still be shut down cleanly"


def test_a_stale_stop_does_not_abort_a_fresh_batch(monkeypatch, project):
    solver = FakeSolver()
    _patch_solver(monkeypatch, solver)
    project.control_path.write_text(json.dumps({"request": "stop"}), encoding="utf-8")
    ts.generate_testset(project, n=3, seed=777)
    assert solver.calls == 3, "a leftover stop file must not cancel the next run"


def test_gives_up_after_consecutive_fem_failures(monkeypatch, project):
    solver = FakeSolver(results=["fem_error"] * 10)
    _patch_solver(monkeypatch, solver)
    ts.generate_testset(project, n=50, seed=777)
    assert solver.calls == ts.MAX_CONSECUTIVE_FAILURES, \
        "a broken solver must not burn through the whole batch"


def test_isolated_failures_do_not_stop_the_batch(monkeypatch, project):
    solver = FakeSolver(results=["ok", "fem_error", "ok", "fem_error", "ok"])
    _patch_solver(monkeypatch, solver)
    ts.generate_testset(project, n=5, seed=777)
    assert solver.calls == 5, "non-consecutive failures are normal, keep going"
