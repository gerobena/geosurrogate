import pandas as pd
import pytest

from geosurrogate.project import Project
from geosurrogate.solvers.demo import load_case_config
from geosurrogate.validation.testset import generate_testset


@pytest.fixture()
def demo_project(tmp_path):
    return Project.create(tmp_path / "proj", load_case_config("slope_2d"))


def test_dry_run_writes_inputs_within_bounds(demo_project):
    path = generate_testset(demo_project, n=25, seed=777, dry_run=True)
    df = pd.read_excel(path)
    cfg = demo_project.config
    assert list(df.columns) == cfg.var_ids
    assert len(df) == 25
    for v in cfg.variables:
        lo, hi = v.training_bounds
        assert df[v.id].between(lo, hi).all()


def test_dry_run_deterministic_per_seed(demo_project):
    a = pd.read_excel(generate_testset(demo_project, n=10, seed=1, dry_run=True))
    b = pd.read_excel(generate_testset(demo_project, n=10, seed=1, dry_run=True))
    c = pd.read_excel(generate_testset(demo_project, n=10, seed=2, dry_run=True))
    assert a.equals(b)
    assert not a.equals(c)


def test_real_run_refused_for_pool_projects(demo_project):
    with pytest.raises(RuntimeError, match="use-pool"):
        generate_testset(demo_project, n=5, seed=1, dry_run=False)
