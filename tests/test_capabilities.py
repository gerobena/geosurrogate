"""RS2 capability detection: what the environment can actually do.

The distinction matters for the public demo. A Linux container can never reach
RS2 (Windows-only licensed software driven as a local process), so the UI must
hide that journey rather than tell the visitor to `pip install RS2Scripting` —
advice that cannot work there. On Windows the same missing package IS
actionable, so the two cases must not collapse into one.
"""

import sys

from geosurrogate.solvers import rs2_available, rs2_supported_platform
from geosurrogate.solvers.rs2 import MODE_ENV


def test_demo_mode_env_forces_unsupported(monkeypatch):
    monkeypatch.setenv(MODE_ENV, "demo")
    assert rs2_supported_platform() is False
    assert rs2_available() is False


def test_demo_mode_env_is_case_insensitive_and_trimmed(monkeypatch):
    monkeypatch.setenv(MODE_ENV, "  DEMO ")
    assert rs2_supported_platform() is False


def test_unset_mode_follows_the_platform(monkeypatch):
    monkeypatch.delenv(MODE_ENV, raising=False)
    assert rs2_supported_platform() is (sys.platform == "win32")


def test_other_mode_values_do_not_force_demo(monkeypatch):
    monkeypatch.setenv(MODE_ENV, "full")
    assert rs2_supported_platform() is (sys.platform == "win32")


def test_availability_implies_supported_platform(monkeypatch):
    monkeypatch.delenv(MODE_ENV, raising=False)
    # Available is the stricter claim: it can never be true where the platform
    # itself rules RS2 out.
    if rs2_available():
        assert rs2_supported_platform()
