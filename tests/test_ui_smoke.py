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


def test_home_hides_the_rs2_journey_in_demo_mode(monkeypatch):
    """The public demo container forces demo mode, where RS2 can never work.

    Offering the from-zero tab there would send visitors down a path that only
    ends in an error telling them to install a package that would not help.
    """
    monkeypatch.setenv("GEOSURROGATE_MODE", "demo")
    at = AppTest.from_file(str(APP / "Home.py"), default_timeout=30)
    at.run()
    assert not at.exception
    assert not at.file_uploader, "the .fez uploader must not be offered in demo mode"


@pytest.mark.parametrize("page", PAGES, ids=[p.stem for p in PAGES])
def test_page_renders_with_project(page, demo_project):
    at = AppTest.from_file(str(page), default_timeout=30)
    at.session_state["project_root"] = demo_project
    at.run()
    assert not at.exception


def test_every_button_has_an_explicit_key():
    """Streamlit derives widget ids from label+params; two buttons with the
    same translated label collide (StreamlitDuplicateElementId) - tabs render
    all their content at once. Enforce an explicit key on every button."""
    import ast

    offenders = []
    for path in [APP / "Home.py", *sorted((APP / "pages").glob("*.py"))]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("button", "download_button")
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "st"):
                if not any(kw.arg == "key" for kw in node.keywords):
                    offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, f"buttons without explicit key: {offenders}"


def test_training_page_shows_trained_banner(tmp_path):
    root = tmp_path / "proj"
    project = Project.create(root, load_case_config("slope_2d"))
    project.write_state(phase="done", status="finished", stop_reason="converged",
                        n_samples=18, iteration=9)
    at = AppTest.from_file(str(APP / "pages" / "5_Training.py"), default_timeout=30)
    at.session_state["project_root"] = str(root)
    at.run()
    assert not at.exception
    assert any("Model trained" in s.value for s in at.success)


def test_validation_page_shows_progress_and_disables_button(tmp_path):
    import datetime as dt
    import json as _json

    root = tmp_path / "proj"
    project = Project.create(root, load_case_config("slope_2d"))
    val_dir = root / "validation"
    val_dir.mkdir()
    (val_dir / "loocv_progress.json").write_text(_json.dumps(
        {"done": 5, "total": 18,
         "ts": dt.datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")
    at = AppTest.from_file(str(APP / "pages" / "6_Validation.py"), default_timeout=30)
    at.session_state["project_root"] = str(root)
    at.run()
    assert not at.exception


def test_exploitation_page_shows_stage_progress(tmp_path):
    import datetime as dt
    import json as _json

    root = tmp_path / "proj"
    project = Project.create(root, load_case_config("slope_2d"))
    exp_dir = root / "exploitation"
    exp_dir.mkdir()
    now = dt.datetime.now().isoformat(timespec="seconds")
    (exp_dir / "mcs_progress.json").write_text(_json.dumps(
        {"stage": "predicting", "started": now, "ts": now}), encoding="utf-8")
    at = AppTest.from_file(str(APP / "pages" / "7_Exploitation.py"),
                           default_timeout=30)
    at.session_state["project_root"] = str(root)
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
