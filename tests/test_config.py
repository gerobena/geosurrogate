import pytest
from pydantic import ValidationError

from geosurrogate.config import ENV_RSCRIPT, ProjectConfig, _WINDOWS_RSCRIPT_DEFAULT


def _minimal(**overrides):
    data = {
        "project": {"name": "t"},
        "solver": {"type": "demo", "demo_case": "slope_2d"},
        "variables": [
            {"id": "cohesion", "material": "M1", "property": "cohesion",
             "training_bounds": [2.0, 6.0],
             "distribution": {"family": "normal", "mean": 4.0, "std": 0.5}},
            {"id": "friction_angle", "material": "M1", "property": "friction_angle",
             "training_bounds": [25.0, 34.0],
             "distribution": {"family": "uniform", "low": 25.0, "high": 34.0}},
        ],
    }
    data.update(overrides)
    return data


def test_minimal_config_valid():
    cfg = ProjectConfig.model_validate(_minimal())
    assert cfg.dims == 2
    assert cfg.var_ids == ["cohesion", "friction_angle"]
    assert cfg.bounds()[0] == (2.0, 6.0)
    assert cfg.exploitation.failure_threshold == 1.0


def test_yaml_roundtrip(tmp_path):
    cfg = ProjectConfig.model_validate(_minimal())
    path = tmp_path / "project.yaml"
    cfg.to_yaml(path)
    again = ProjectConfig.from_yaml(path)
    assert again == cfg


def test_reversed_bounds_rejected():
    bad = _minimal()
    bad["variables"][0]["training_bounds"] = [6.0, 2.0]
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate(bad)


def test_duplicate_variable_ids_rejected():
    bad = _minimal()
    bad["variables"][1]["id"] = "cohesion"
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate(bad)


def test_demo_solver_requires_case():
    bad = _minimal(solver={"type": "demo"})
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate(bad)


def test_distribution_family_params_enforced():
    bad = _minimal()
    bad["variables"][0]["distribution"] = {"family": "triangular", "low": 1.0, "high": 2.0}
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate(bad)


def test_rscript_default_falls_back_to_windows_path(monkeypatch):
    monkeypatch.delenv(ENV_RSCRIPT, raising=False)
    cfg = ProjectConfig.model_validate(_minimal())
    assert cfg.solver.rscript_path == _WINDOWS_RSCRIPT_DEFAULT


def test_rscript_env_override_honoured(monkeypatch, tmp_path):
    # an explicit path in the env is used verbatim (CI / non-Windows machines)
    fake = tmp_path / "Rscript"
    fake.write_text("")
    monkeypatch.setenv(ENV_RSCRIPT, str(fake))
    cfg = ProjectConfig.model_validate(_minimal())
    assert cfg.solver.rscript_path == fake


def test_explicit_rscript_path_beats_env(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_RSCRIPT, str(tmp_path / "from_env"))
    cfg = ProjectConfig.model_validate(
        _minimal(solver={"type": "demo", "demo_case": "slope_2d",
                         "rscript_path": r"C:\explicit\Rscript.exe"}))
    assert str(cfg.solver.rscript_path) == r"C:\explicit\Rscript.exe"
