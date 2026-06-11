"""The guided-flow breadcrumb walks the user through the whole journey."""

import json

import pytest

from geosurrogate.project import Project
from geosurrogate.solvers.demo import load_case_config
from geosurrogate.ui.common import compute_next_step


@pytest.fixture()
def project(tmp_path):
    return Project.create(tmp_path / "proj", load_case_config("slope_2d"))


def _label(project):
    return compute_next_step(project)[1]


def test_full_journey(project):
    # fresh project -> start training
    assert _label(project) == "next.start_training"

    project.write_state(status="running", phase="doe", n_samples=3)
    assert _label(project) == "next.watch_training"

    project.write_state(status="running", phase="auto_validation")
    assert _label(project) == "next.validating"

    project.write_state(status="paused", phase="active_learning")
    assert _label(project) == "next.resume_training"

    project.write_state(status="finished", phase="done", n_samples=12,
                        stop_reason="converged")
    assert _label(project) == "next.run_loocv"

    val = project.root / "validation"
    val.mkdir(exist_ok=True)
    (val / "loocv_metrics.json").write_text(json.dumps({"r2": 1.0}))
    assert _label(project) == "next.independent"

    (val / "massive_metrics.json").write_text(json.dumps({"r2": 1.0}))
    assert _label(project) == "next.exploit"

    exp = project.root / "exploitation"
    exp.mkdir(exist_ok=True)
    (exp / "mcs_metrics.json").write_text(json.dumps({"pof": 0.1}))
    assert _label(project) == "next.report"

    rep = project.root / "report"
    rep.mkdir(exist_ok=True)
    (rep / "report_20260611_000000.html").write_text("<html></html>")
    assert _label(project) == "next.done"
