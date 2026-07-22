"""RS2 (Rocscience) adapter: drives RS2 Modeler + Interpreter via RS2Scripting.

Ported from the TFM ingest/orchestrator scripts with the design upgrades
agreed in ARQUITECTURA.md: materials resolved BY NAME (not by index), no
global taskkill (we only manage the instances we start), typed CaseResult
instead of "ERROR" strings, and configurable executable overrides.

Version coupling note: the RS2Scripting package version must match the
installed RS2 generation (the package locates RS2 through the Windows
registry key of its own generation, e.g. 'RS2 11.0'). Install the package
version that corresponds to the user's RS2: pip install RS2Scripting==<ver>.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from ..config import ProjectConfig
from .base import CaseResult, MaterialInfo

START_TIMEOUT_S = 90  # license checkout on first start can be slow

# Set GEOSURROGATE_MODE=demo to force demo mode regardless of the host (the
# container/public demo does this: offering RS2 there would only ever fail).
MODE_ENV = "GEOSURROGATE_MODE"


class RS2NotAvailable(RuntimeError):
    pass


class RS2ConnectionError(RuntimeError):
    pass


def _import_rs2():
    try:
        from rs2.interpreter.RS2Interpreter import RS2Interpreter
        from rs2.modeler.properties.PropertyEnums import (MaterialType,
                                                          StrengthCriteriaTypes)
        from rs2.modeler.RS2Modeler import RS2Modeler
    except ImportError as e:
        raise RS2NotAvailable(
            "The RS2Scripting package is not installed in this environment. "
            "Install the version matching your RS2 installation, e.g.: "
            "pip install RS2Scripting==11.28.0"
        ) from e
    return RS2Modeler, RS2Interpreter, MaterialType, StrengthCriteriaTypes


def rs2_supported_platform() -> bool:
    """Whether RS2 could ever be driven from this environment.

    False in a Linux container or when demo mode is forced: RS2 is licensed
    Windows software that the adapter reaches as a local process, so there no
    amount of installing RS2Scripting would help. Callers use this to hide the
    RS2 path outright instead of advertising one that cannot work.
    """
    if os.environ.get(MODE_ENV, "").strip().lower() == "demo":
        return False
    return sys.platform == "win32"


def rs2_available() -> bool:
    """Whether RS2 can actually be driven right now (platform *and* package).

    A supported platform with the package missing is recoverable — the user can
    install the RS2Scripting build matching their RS2 — which is why that case
    is kept distinct from `rs2_supported_platform`.
    """
    if not rs2_supported_platform():
        return False
    try:
        _import_rs2()
    except RS2NotAvailable:
        return False
    return True


# --- process lifecycle ------------------------------------------------------
# RS2Scripting's closeProgram() sends the close request and then busy-waits for
# the port to free, raising TimeoutError after 30 s. Swallowing that leaves an
# orphan RS2 holding 60054/60055 and the *next* run dies with an unexplained
# "port is occupied". So every close is verified, and anything we started that
# survives is terminated BY PID — never by image name, which would also kill the
# user's own RS2 session.

def _rs2_process_ids() -> set[int]:
    """PIDs of live RS2 / Interpret processes (Windows only)."""
    if sys.platform != "win32":
        return set()
    pids: set[int] = set()
    for image in ("RS2.exe", "Interpret.exe"):
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=20).stdout
        except Exception:
            continue
        for line in out.splitlines():
            fields = [f.strip('"') for f in line.split('","')]
            if len(fields) >= 2 and fields[1].isdigit():
                pids.add(int(fields[1]))
    return pids


def _force_close(pids: set[int]) -> list[int]:
    """Terminate exactly these PIDs. Returns the ones actually killed."""
    killed = []
    for pid in sorted(pids):
        res = subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                             capture_output=True, text=True)
        if res.returncode == 0:
            killed.append(pid)
    return killed


def _close_app(app, label: str) -> str:
    """Ask the app to close. Returns "" if it obeyed, else a short reason.

    Nothing is printed here: RS2 routinely refuses ("Please close all open
    dialogs before closing the program") and _reap then terminates it, so
    shouting about the refusal *and* the cleanup would put two alarming lines
    in the log for what is ordinary housekeeping.
    """
    try:
        app.closeProgram(False)
    except TypeError:  # older signature without the saveModels flag
        try:
            app.closeProgram()
        except Exception as e:
            return _reason(e)
    except Exception as e:
        return _reason(e)
    return ""


def _reason(e: Exception) -> str:
    return str(e).strip().rstrip(".") or e.__class__.__name__


def _reap(owned: set[int], label: str, reason: str = "") -> None:
    """Terminate leftovers among the instances we started, in one calm line."""
    leftover = owned & _rs2_process_ids()
    if not leftover:
        return
    killed = _force_close(leftover)
    detail = f" - {reason}" if reason else ""
    if killed:
        print(f"{label}: kept the ports open, closed PID(s) {killed}{detail}",
              flush=True)
    else:
        print(f"warning: {label} is still running (PID(s) {sorted(leftover)}) and "
              f"could not be closed{detail}; close it manually or the next RS2 "
              f"run will fail with 'port is occupied'", flush=True)


def _extract_materials(model) -> list[MaterialInfo]:
    out = []
    for i, mat in enumerate(model.getAllMaterialProperties()):
        name = mat.getMaterialName()
        current: dict[str, float] = {}
        criterion = "unknown"
        try:
            mc = mat.Strength.MohrCoulombStrength
            current = {
                "peak_cohesion": float(mc.getPeakCohesion()),
                "peak_friction_angle": float(mc.getPeakFrictionAngle()),
            }
            criterion = "mohr_coulomb"
        except Exception:
            pass
        out.append(MaterialInfo(name=name, index=i, criterion=criterion,
                                current_values=current))
    return out


def discover_materials(model_path: Path, port: int = 60054,
                       modeler_executable: Path | None = None) -> list[MaterialInfo]:
    """One-shot material discovery for the from-zero wizard: start RS2 Modeler,
    open the model, list materials with current values, shut everything down.
    Requires a licensed RS2 installation on this machine."""
    RS2Modeler, _i, _mt, _sc = _import_rs2()
    model_path = Path(model_path).resolve()
    if not model_path.exists():
        raise FileNotFoundError(f"FEM model not found: {model_path}")
    before = _rs2_process_ids()
    try:
        RS2Modeler.startApplication(
            port=port,
            overridePathToExecutable=(str(modeler_executable)
                                      if modeler_executable else None),
            timeout=START_TIMEOUT_S)
        modeler = RS2Modeler(port=port)
    except (FileNotFoundError, TimeoutError, RuntimeError) as e:
        _reap(_rs2_process_ids() - before, "RS2 Modeler")
        raise RS2ConnectionError(
            f"{e} - check that RS2 is installed and licensed, that port {port} "
            f"is free (close stale RS2/Interpret processes), or set an "
            f"executable override.") from e
    owned = _rs2_process_ids() - before
    try:
        model = modeler.openFile(str(model_path))
        try:
            return _extract_materials(model)
        finally:
            model.close()
    finally:
        # Leaving this instance alive would block the very next step (training
        # reuses the same port), which is exactly what used to happen.
        _reap(owned, "RS2 Modeler", _close_app(modeler, "RS2 Modeler"))


class RS2Solver:
    is_pool_based = False

    def __init__(self, config: ProjectConfig):
        (self._RS2Modeler, self._RS2Interpreter,
         self._MaterialType, self._StrengthCriteriaTypes) = _import_rs2()
        self.config = config
        self.model_path = Path(config.solver.model_file).resolve()
        if not self.model_path.exists():
            raise FileNotFoundError(f"base FEM model not found: {self.model_path}")
        self._varmap = {v.id: (v.material, v.property) for v in config.variables}
        self._modeler = None
        self._interpreter = None
        self._owned_pids: set[int] = set()

    # --- lifecycle --------------------------------------------------------
    def connect(self) -> None:
        s = self.config.solver
        before = _rs2_process_ids()
        try:
            self._RS2Modeler.startApplication(
                port=s.ports.modeler,
                overridePathToExecutable=(str(s.rs2_modeler_executable)
                                          if s.rs2_modeler_executable else None),
                timeout=START_TIMEOUT_S)
            self._modeler = self._RS2Modeler(port=s.ports.modeler)
            self._RS2Interpreter.startApplication(
                port=s.ports.interpreter,
                overridePathToExecutable=(str(s.rs2_interpreter_executable)
                                          if s.rs2_interpreter_executable else None),
                timeout=START_TIMEOUT_S)
            self._interpreter = self._RS2Interpreter(port=s.ports.interpreter)
            self._owned_pids = _rs2_process_ids() - before
        except FileNotFoundError as e:
            # A partial start (Modeler up, Interpreter failed) must not leak.
            _reap(_rs2_process_ids() - before, "RS2")
            raise RS2ConnectionError(
                "RS2 installation not found via the Windows registry. Is RS2 "
                "installed? On non-standard installs, set solver."
                "rs2_modeler_executable / rs2_interpreter_executable in "
                "project.yaml.") from e
        except TimeoutError as e:
            _reap(_rs2_process_ids() - before, "RS2")
            raise RS2ConnectionError(
                f"RS2 did not become ready within {START_TIMEOUT_S}s. Check "
                f"that the license is available and that ports "
                f"{s.ports.modeler}/{s.ports.interpreter} are free (close "
                f"stale RS2 instances or change solver.ports).") from e
        except RuntimeError as e:
            _reap(_rs2_process_ids() - before, "RS2")
            # RS2Scripting raises a plain RuntimeError when the port is taken,
            # typically by RS2/Interpret instances left behind by an aborted
            # run (Ctrl+C kills Python before its shutdown() runs).
            raise RS2ConnectionError(
                f"{e} Likely cause: stale 'RS2' or 'Interpret' processes from "
                f"a previous aborted run - close them in Task Manager, or set "
                f"different ports in solver.ports of project.yaml.") from e

    def shutdown(self) -> None:
        reasons: list[str] = []
        for app, label in ((self._modeler, "RS2 Modeler"),
                           (self._interpreter, "RS2 Interpreter")):
            if app is not None:
                why = _close_app(app, label)
                if why:
                    reasons.append(why)
        self._modeler = None
        self._interpreter = None
        # Verify: a refused or timed-out close leaves the port held, and the
        # next run (or the user's next click) would fail with "port occupied".
        _reap(self._owned_pids, "RS2", "; ".join(dict.fromkeys(reasons)))
        self._owned_pids = set()

    # --- discovery --------------------------------------------------------
    def list_materials(self) -> list[MaterialInfo]:
        model = self._modeler.openFile(str(self.model_path))
        try:
            return _extract_materials(model)
        finally:
            model.close()

    # --- execution --------------------------------------------------------
    def run_case(self, assignments: dict[str, float], workdir: Path, case_id: str) -> CaseResult:
        t0 = time.time()
        workdir = Path(workdir).resolve()  # RS2 resolves paths from its own cwd
        workdir.mkdir(parents=True, exist_ok=True)
        out_path = workdir / f"{case_id}.fez"

        # group values per material: {material_name: {property: value}}
        touched: dict[str, dict[str, float]] = {}
        for var_id, value in assignments.items():
            mat_name, prop = self._varmap[var_id]
            touched.setdefault(mat_name, {})[prop] = float(value)

        model = None
        try:
            model = self._modeler.openFile(str(self.model_path))
            by_name = {m.getMaterialName(): m for m in model.getAllMaterialProperties()}
            missing = [n for n in touched if n not in by_name]
            if missing:
                raise KeyError(f"materials {missing} not found in model; "
                               f"available: {sorted(by_name)}")
            for mat_name, props in touched.items():
                mat = by_name[mat_name]
                mc = mat.Strength.MohrCoulombStrength
                mc.setMaterialType(self._MaterialType.PLASTIC)
                mat.Strength.setFailureCriterion(self._StrengthCriteriaTypes.MOHR_COULOMB)
                if "cohesion" in props:
                    mc.setPeakCohesion(props["cohesion"])
                    mc.setResidualCohesion(props["cohesion"])
                if "friction_angle" in props:
                    mc.setPeakFrictionAngle(props["friction_angle"])
                    mc.setResidualFrictionAngle(props["friction_angle"])
            model.saveAs(str(out_path))
            model.compute()
            model.close()
            model = None
        except Exception as e:
            if model is not None:
                try:
                    model.close()
                except Exception:
                    pass
            return CaseResult(case_id=case_id, srf=None, status="fem_error",
                              elapsed_s=time.time() - t0,
                              message=f"modeler/compute: {e!r}"[:500])

        result_model = None
        try:
            result_model = self._interpreter.openFile(str(out_path))
            srf = float(result_model.getCriticalSRF())
            result_model.close()
        except Exception as e:
            if result_model is not None:
                try:
                    result_model.close()
                except Exception:
                    pass
            return CaseResult(case_id=case_id, srf=None, status="fem_error",
                              elapsed_s=time.time() - t0, fem_file=out_path,
                              message=f"interpreter: {e!r}"[:500])

        retention = self.config.solver.fem_retention
        kept: Path | None = out_path
        if retention == "keep_none" or (retention == "keep_failed"):
            # keep_failed keeps only failing cases; this one succeeded
            out_path.unlink(missing_ok=True)
            kept = None
        return CaseResult(case_id=case_id, srf=srf, status="ok",
                          elapsed_s=time.time() - t0, fem_file=kept)
