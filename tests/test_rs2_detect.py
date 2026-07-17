"""RS2 auto-detection: the registry-build -> RS2Scripting mapping.

The mapping is the Phase-C linchpin (installer picks the right package with no
hand-kept table), so its logic is pinned here. Registry reads are Windows-only
and machine-dependent, so detect_rs2_installations() is only checked for shape.
"""

import sys

import pytest

from geosurrogate.rs2_detect import (detect_rs2_installations,
                                     scripting_spec_for, select_pypi_version)


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
