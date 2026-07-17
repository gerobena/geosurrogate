"""Detect the installed RS2 generation and derive the matching RS2Scripting.

Phase C groundwork. RS2Scripting must match the installed RS2 generation because
the package locates RS2 through that generation's Windows registry key. Rather
than maintain a hand-kept table, we read the generation straight from the
registry and derive the pip requirement from it.

Empirically (verified on RS2 11.028 with RS2Scripting 11.28.0):

    HKLM\\SOFTWARE\\Rocscience\\RS2 11.0
        Version         = 11.028      -> RS2Scripting 11.28.*
        Install         = C:\\Program Files\\Rocscience\\RS2
        PythonInstalled = True        (RS2's own scripting component is present)

So the build's zero-padded minor ("028") is the package minor (28), and we ask
pip for the latest patch of that minor: RS2Scripting==11.28.*. The registry read
is Windows-only; everywhere else detection yields an empty list, so this module
imports cleanly on Linux/CI.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

PYPI_JSON_URL = "https://pypi.org/pypi/RS2Scripting/json"

# "RS2 11.0", "RS2 12.0" — the generation subkeys under HKLM\SOFTWARE\Rocscience.
# The trailing space guards against matching "RS2", "RS3", "RSData", etc.
_RS2_SUBKEY = re.compile(r"^RS2 \d")


@dataclass(frozen=True)
class RS2Install:
    generation: str          # registry subkey name, e.g. "RS2 11.0"
    version: str             # build string from the registry, e.g. "11.028"
    install_path: Path | None
    python_installed: bool   # RS2's own Python scripting component present
    scripting_spec: str      # pip requirement, e.g. "RS2Scripting==11.28.*"

    @property
    def pip_command(self) -> str:
        return f'pip install "{self.scripting_spec}"'


def scripting_spec_for(version: str) -> str:
    """Map an RS2 build string to a pip requirement for RS2Scripting.

    The build's major.minor drives it; the zero-padded minor is read as an int,
    so "11.028" -> "RS2Scripting==11.28.*" (latest patch of that minor). Raises
    ValueError if the string is not <major>.<minor>[...] with numeric parts.
    """
    parts = version.strip().split(".")
    if len(parts) < 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        raise ValueError(f"unrecognized RS2 version string: {version!r}")
    major, minor = int(parts[0]), int(parts[1])
    return f"RS2Scripting=={major}.{minor}.*"


def select_pypi_version(available: list[str], version: str) -> str | None:
    """Latest published RS2Scripting patch matching the RS2 build's minor.

    `available` is the list of versions on PyPI. Returns the highest x.y.z whose
    x.y equals the build's major.minor, or None if that minor was never
    published (the caller then warns instead of failing silently).
    """
    parts = version.strip().split(".")
    if len(parts) < 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        raise ValueError(f"unrecognized RS2 version string: {version!r}")
    target = (int(parts[0]), int(parts[1]))

    def _key(v: str) -> tuple[int, int, int] | None:
        m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", v)
        return (int(m[1]), int(m[2]), int(m[3])) if m else None

    matches = [k for v in available if (k := _key(v)) and k[:2] == target]
    if not matches:
        return None
    best = max(matches)
    return f"{best[0]}.{best[1]}.{best[2]}"


def detect_rs2_installations() -> list[RS2Install]:
    """Every RS2 generation registered on this machine, newest build first.

    Empty on non-Windows (winreg absent) and when Rocscience keys are missing.
    Reads the 64-bit registry view explicitly so a 32-bit Python still sees the
    (64-bit) RS2 keys.
    """
    if sys.platform != "win32":
        return []
    import winreg

    found: list[RS2Install] = []
    access = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                              r"SOFTWARE\Rocscience", 0, access)
    except OSError:
        return []

    with root:
        for i in range(_subkey_count(root)):
            try:
                name = winreg.EnumKey(root, i)
            except OSError:
                break
            if not _RS2_SUBKEY.match(name):
                continue
            inst = _read_generation(winreg, root, name, access)
            if inst is not None:
                found.append(inst)

    found.sort(key=lambda r: _version_sort_key(r.version), reverse=True)
    return found


def _subkey_count(key) -> int:
    import winreg
    return winreg.QueryInfoKey(key)[0]


def _read_generation(winreg, root, name: str, access):
    try:
        with winreg.OpenKey(root, name, 0, access) as gen:
            version = _read_value(winreg, gen, "Version")
            if not version:
                return None
            install = _read_value(winreg, gen, "Install")
            py = _read_value(winreg, gen, "PythonInstalled")
            try:
                spec = scripting_spec_for(version)
            except ValueError:
                return None
            return RS2Install(
                generation=name,
                version=version,
                install_path=Path(install) if install else None,
                python_installed=str(py).strip().lower() in ("true", "1"),
                scripting_spec=spec,
            )
    except OSError:
        return None


def _read_value(winreg, key, value_name: str):
    try:
        return winreg.QueryValueEx(key, value_name)[0]
    except OSError:
        return None


def _version_sort_key(version: str) -> tuple[int, ...]:
    return tuple(int(p) if p.isdigit() else 0 for p in version.split("."))


def fetch_pypi_versions() -> list[str]:
    """Published RS2Scripting versions from PyPI (network). [] on any failure."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(PYPI_JSON_URL, timeout=10) as resp:
            data = json.load(resp)
        return list(data.get("releases", {}).keys())
    except Exception:
        return []
