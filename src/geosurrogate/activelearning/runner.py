"""JobRunner: launch/observe/pause a loop process. The UI (F2) talks only to
this module and to the state/events files — never to the loop directly."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def launch_detached(project_root: Path | str) -> int:
    """Start `geosurrogate run <project>` as a detached process; returns its PID."""
    root = Path(project_root)
    log = open(root / "log" / "runner.out", "a", encoding="utf-8")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, "-m", "geosurrogate.cli", "run", str(root)],
        stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
    )
    return proc.pid


def request_pause(project_root: Path | str) -> None:
    control = Path(project_root) / "control.json"
    control.write_text(json.dumps({"request": "pause"}), encoding="utf-8")
