"""End-to-end test: full DOE + active-learning loop on the slope_2d demo case.

Requires a local R installation with deepgp (path taken from the case config).
Skipped automatically when R is absent so the rest of the suite stays green.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from geosurrogate.config import ProjectConfig
from geosurrogate.project import Project
from geosurrogate.activelearning import loop
from geosurrogate.solvers.demo import demo_cases_dir, load_case_config


def _r_available() -> bool:
    try:
        cfg = load_case_config("slope_2d")
    except Exception:
        return False
    return Path(cfg.solver.rscript_path).exists()


pytestmark = pytest.mark.e2e


@pytest.mark.skipif(not _r_available(), reason="R/deepgp not available or demo data not packaged")
def test_slope_2d_short_run(tmp_path):
    cfg = load_case_config("slope_2d")
    data = cfg.model_dump(mode="json")
    doe_total = data["doe"]["n_lhs"] + data["doe"]["n_pem"]
    data["active_learning"]["budget_total_sims"] = doe_total + 3
    data["active_learning"]["validation_grid"]["n"] = 800
    data["surrogate"]["mcmc"] = {"nmcmc": 800, "burn": 250, "thin": 2}
    cfg = ProjectConfig.model_validate(data)

    project = Project.create(tmp_path / "run", cfg)
    reason = loop.run(project)

    assert reason in ("budget_exhausted", "converged", "max_iterations")
    ds = project.load_dataset()
    assert (ds["status"] == "ok").sum() >= doe_total + 1
    assert ds["srf"].notna().all()

    events = [json.loads(l) for l in project.events_path.read_text().splitlines()]
    al_iters = [e for e in events if e["type"] == "al_iteration"]
    assert len(al_iters) >= 1
    assert any(e.get("error_max") is not None for e in al_iters[1:]) or len(al_iters) == 1

    # every demo SRF must come from the real pool
    lookup = pd.read_csv(demo_cases_dir() / "slope_2d" / "lookup.csv")
    assert set(ds["srf"].round(6)) <= set(lookup["srf"].round(6))
