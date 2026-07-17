"""RS2 auto-detection: the registry-build -> RS2Scripting mapping.

The mapping is the Phase-C linchpin (installer picks the right package with no
hand-kept table), so its logic is pinned here. Registry reads are Windows-only
and machine-dependent, so detect_rs2_installations() is only checked for shape.
"""

import sys

import pytest
from typer.testing import CliRunner

from geosurrogate import rs2_detect
from geosurrogate.cli import app
from geosurrogate.rs2_detect import (RS2Install, detect_rs2_installations,
                                     scripting_spec_for, scripting_target,
                                     select_pypi_version)

runner = CliRunner()


def _fake_install(version="11.028", python_installed=True):
    return RS2Install(
        generation="RS2 11.0", version=version, install_path=None,
        python_installed=python_installed,
        scripting_spec=scripting_spec_for(version))


@pytest.mark.parametrize("build, spec", [
    ("11.028", "RS2Scripting==11.28.*"),   # the verified real case
    ("11.023", "RS2Scripting==11.23.*"),   # oldest published minor
    ("11.29", "RS2Scripting==11.29.*"),    # unpadded minor
    ("12.003", "RS2Scripting==12.3.*"),    # a future generation
    ("11.028.1", "RS2Scripting==11.28.*"),  # extra components are ignored
])
def test_scripting_spec_mapping(build, spec):
    assert scripting_spec_for(build) == spec


@pytest.mark.parametrize("bad", ["", "11", "eleven.0", "11.x", "v11.028"])
def test_scripting_spec_rejects_garbage(bad):
    with pytest.raises(ValueError):
        scripting_spec_for(bad)


def test_select_pypi_picks_latest_patch_of_the_minor():
    available = ["11.23.0", "11.28.0", "11.28.2", "11.28.1", "11.29.0"]
    # 11.028 -> minor 28 -> highest 11.28.z, not the globally latest 11.29.0
    assert select_pypi_version(available, "11.028") == "11.28.2"


def test_select_pypi_returns_none_when_minor_absent():
    available = ["11.28.0", "11.29.0"]
    assert select_pypi_version(available, "11.030") is None


def test_select_pypi_ignores_nonstandard_version_strings():
    available = ["11.28.0", "11.28.0rc1", "garbage", "11.28.1"]
    assert select_pypi_version(available, "11.028") == "11.28.1"


def test_detect_is_shape_stable_and_linux_safe():
    installs = detect_rs2_installations()
    assert isinstance(installs, list)
    if sys.platform != "win32":
        assert installs == []  # no winreg off Windows
    for inst in installs:
        assert inst.scripting_spec.startswith("RS2Scripting==")
        assert inst.pip_command.startswith("pip install ")


@pytest.mark.parametrize("version, target", [
    ("11.028", (11, 28)), ("11.28.0", (11, 28)), ("12.003", (12, 3))])
def test_scripting_target(version, target):
    assert scripting_target(version) == target


# --- setup-rs2 command (detection mocked; pip is never actually run) ---------
def test_setup_rs2_errors_without_rs2(monkeypatch):
    monkeypatch.setattr(rs2_detect, "detect_rs2_installations", lambda: [])
    result = runner.invoke(app, ["setup-rs2"])
    assert result.exit_code == 1
    assert "No RS2 installation found" in result.output


def test_setup_rs2_is_a_noop_when_already_matching(monkeypatch):
    monkeypatch.setattr(rs2_detect, "detect_rs2_installations",
                        lambda: [_fake_install("11.028")])
    monkeypatch.setattr(rs2_detect, "installed_scripting_version", lambda: "11.28.0")
    result = runner.invoke(app, ["setup-rs2", "--yes"])
    assert result.exit_code == 0
    assert "already matches" in result.output


def test_setup_rs2_dry_run_shows_command_without_installing(monkeypatch):
    monkeypatch.setattr(rs2_detect, "detect_rs2_installations",
                        lambda: [_fake_install("11.028")])
    monkeypatch.setattr(rs2_detect, "installed_scripting_version", lambda: None)
    result = runner.invoke(app, ["setup-rs2", "--dry-run"])
    assert result.exit_code == 0
    assert 'RS2Scripting==11.28.*' in result.output
    assert "dry run" in result.output


def test_setup_rs2_flags_a_version_mismatch(monkeypatch):
    monkeypatch.setattr(rs2_detect, "detect_rs2_installations",
                        lambda: [_fake_install("11.028")])
    monkeypatch.setattr(rs2_detect, "installed_scripting_version", lambda: "11.27.0")
    result = runner.invoke(app, ["setup-rs2", "--dry-run"])
    assert result.exit_code == 0
    assert "does not match" in result.output
    assert 'RS2Scripting==11.28.*' in result.output


def test_setup_rs2_warns_when_scripting_component_missing(monkeypatch):
    monkeypatch.setattr(rs2_detect, "detect_rs2_installations",
                        lambda: [_fake_install("11.028", python_installed=False)])
    monkeypatch.setattr(rs2_detect, "installed_scripting_version", lambda: None)
    result = runner.invoke(app, ["setup-rs2", "--dry-run"])
    assert "scripting component is not installed" in result.output
