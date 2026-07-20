"""Build a self-contained R + deepgp bundle for the native Windows installer.

The native (RS2) product cannot use Docker, so its installer ships its own R and
the user never installs R. This script produces that bundle: a relocatable copy
of R with deepgp (and only the packages it needs) pre-installed as CRAN Windows
*binaries* — no compilation, no Rtools. R derives R_HOME from its own path, so
the copy runs from wherever the installer drops it (verified 2026-07-17).

Two prunes keep it lean and deterministic:
  * packages    — keep base + recommended + deepgp + deepgp's deps; drop whatever
                  extra packages happen to sit in the build machine's R.
  * within each — drop headless-useless docs/help/tests/examples/i18n, plus the
                  R-root doc/tests/Tcl trees.

Re-runnable. Windows only (that is where the native product runs). Point it at
the source R with --r-home, the GEOSURROGATE_R_HOME env var, or let it auto-
detect from the registry.

  python tools/build_r_bundle.py [--r-home DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Dropped from every kept package (useless for a headless bridge).
PKG_PRUNE = ("help", "html", "doc", "tests", "examples", "po")
# Dropped from the R root.
ROOT_PRUNE = ("doc", "tests", "Tcl")


def detect_r_home() -> Path | None:
    env = os.environ.get("GEOSURROGATE_R_HOME")
    if env:
        return Path(env)
    if sys.platform != "win32":
        return None
    import winreg
    for sub in (r"SOFTWARE\R-core\R64", r"SOFTWARE\R-core\R"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub, 0,
                                winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                path, _ = winreg.QueryValueEx(key, "InstallPath")
        except OSError:
            continue
        if path and Path(path).exists():
            return Path(path)
    return None


def dir_size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024 ** 2


def rscript(bundle: Path, expr: str) -> subprocess.CompletedProcess:
    exe = bundle / "bin" / "Rscript.exe"
    return subprocess.run([str(exe), "-e", expr], capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the R + deepgp bundle.")
    ap.add_argument("--r-home", type=Path, default=None,
                    help="Source R installation (else GEOSURROGATE_R_HOME or registry).")
    ap.add_argument("--out", type=Path, default=REPO / "dist" / "R",
                    help="Bundle output directory (default: dist/R).")
    args = ap.parse_args()

    src = args.r_home or detect_r_home()
    if not src or not src.exists():
        print("ERROR: no source R found. Pass --r-home or set GEOSURROGATE_R_HOME.")
        return 1
    if not (src / "bin" / "Rscript.exe").exists():
        print(f"ERROR: {src} is not an R install (no bin/Rscript.exe).")
        return 1

    out = args.out
    print(f"Source R : {src}")
    print(f"Bundle   : {out}\n")

    # 1. Fresh relocatable copy of R.
    if out.exists():
        print("Removing existing bundle...")
        shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    print("Copying R (a few hundred MB)...")
    shutil.copytree(src, out)
    print(f"  copied: {dir_size_mb(out):.0f} MB\n")

    # 2. Install deepgp into the copy from CRAN as a Windows binary (no compile).
    print("Installing deepgp into the bundle (CRAN binary)...")
    r = rscript(out, 'options(repos="https://cloud.r-project.org", pkgType="binary"); '
                     'install.packages("deepgp", lib=file.path(R.home(),"library")); '
                     'cat("VERSION", as.character(packageVersion("deepgp")))')
    if r.returncode != 0 or "VERSION" not in r.stdout:
        print("ERROR installing deepgp:\n", r.stdout, "\n", r.stderr)
        return 1
    print(f"  deepgp {r.stdout.split('VERSION')[-1].strip()}\n")

    # 3. Prune non-essential packages (keep base + recommended + deepgp + deps).
    r = rscript(out, 'cat(unique(c(rownames(installed.packages('
                     'priority=c("base","recommended"))), "deepgp", '
                     'tools::package_dependencies("deepgp", db=installed.packages(), '
                     'recursive=TRUE)[[1]])), sep=" ")')
    keep = set(r.stdout.split())
    if len(keep) < 10:
        print("ERROR: keep-set looks wrong:", keep, "\n", r.stderr)
        return 1
    lib = out / "library"
    removed = 0
    for pkg in lib.iterdir():
        if pkg.is_dir() and (pkg / "DESCRIPTION").exists() and pkg.name not in keep:
            shutil.rmtree(pkg)
            removed += 1
    print(f"Pruned {removed} extra packages; kept {len(keep)} "
          "(base + recommended + deepgp + deps).")

    # 4. Prune docs/help/tests/i18n inside kept packages, and the R-root trees.
    for pkg in lib.iterdir():
        if pkg.is_dir():
            for sub in PKG_PRUNE:
                shutil.rmtree(pkg / sub, ignore_errors=True)
    for sub in ROOT_PRUNE:
        shutil.rmtree(out / sub, ignore_errors=True)
    print(f"Pruned per-package docs/tests and R root {ROOT_PRUNE}.\n")

    # 5. Prove the pruned bundle still trains a GP.
    print("Smoke test: fitting a GP from the pruned bundle...")
    r = rscript(out, 'suppressPackageStartupMessages(library(deepgp)); '
                     'set.seed(1); x<-matrix(runif(20),10,2); '
                     'fit_one_layer(x, runif(10), nmcmc=40, verb=FALSE); '
                     'cat("SMOKE_OK")')
    if r.returncode != 0 or "SMOKE_OK" not in r.stdout:
        print("ERROR: bundle smoke test FAILED:\n", r.stdout, "\n", r.stderr)
        return 1

    print(f"  passed.\n\nDONE. Bundle at {out} — {dir_size_mb(out):.0f} MB")
    print(f"Point GEOSURROGATE_RSCRIPT at: {out / 'bin' / 'Rscript.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
