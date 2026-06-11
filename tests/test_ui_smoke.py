"""Streamlit smoke tests: every page must render without exceptions against a
freshly created demo project (no training run needed). Uses Streamlit's
AppTest, so no browser or server is involved."""

from pathlib import Path

import pytest

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from geosurrogate.project import Project
from geosurrogate.solvers.demo import load_case_config

APP = Path(__file__).resolve().parents[1] / "app"
PAGES = sorted((APP / "pages").glob("*.py"))


@pytest.fixture(scope="module")
def demo_project(tmp_path_factory):
    root = tmp_path_factory.mktemp("ui") / "proj"
    Project.create(root, load_case_config("slope_2d"))
    return str(root)


def test_home_renders_without_project():
    at = AppTest.from_file(str(APP / "Home.py"), default_timeout=30)
    at.run()
    assert not at.exception


@pytest.mark.parametrize("page", PAGES, ids=[p.stem for p in PAGES])
def test_page_renders_with_project(page, demo_project):
    at = AppTest.from_file(str(page), default_timeout=30)
    at.session_state["project_root"] = demo_project
    at.run()
    assert not at.exception


def test_training_page_renders_mid_doe_phase(tmp_path):
    """Regression: right after Start, events exist but none carries error_max
    yet (DoE phase) - the live chart must not crash on the missing column."""
    root = tmp_path / "proj"
    project = Project.create(root, load_case_config("slope_2d"))
    project.append_event("phase_change", phase="doe", target=9, done=0)
    project.append_event("doe_case_done", case_id="Case_0001", srf=1.0,
                         status="ok", elapsed_s=0.1, message=None)
    at = AppTest.from_file(str(APP / "pages" / "5_Training.py"), default_timeout=30)
    at.session_state["project_root"] = str(root)
    at.run()
    assert not at.exception
