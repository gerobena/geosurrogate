"""Build a self-contained Python + geosurrogate bundle for the native installer.

Companion to build_r_bundle.py. The native product ships its own Python so the
user installs nothing; we bundle an embeddable CPython rather than freezing with
PyInstaller because the app spawns `sys.executable -m geosurrogate.cli` detached
processes and resolves app/ + demo_cases/ from the repo root — both keep working
verbatim when sys.executable is a real python.exe and the repo layout is intact.

Output layout (dist/ is the canonical install root; R lands beside it):

    dist/
      python/        embeddable CPython + [ui] deps + a RELATIVE geosurrogate.pth
      src/ app/ demo_cases/ pyproject.toml README.md   (copied repo layout)
      R/             (from build_r_bundle.py, if already built)

Relocatability: the .pth entry is `..\..\..\src` resolved from site-packages, so
`import geosurrogate` finds dist/src wherever the installer drops dist/, and
REPO_DIR (= parents[3] of .../ui/common.py) lands on dist/, where app/ and
demo_cases/ live. No absolute paths baked in.

Re-runnable. Windows only. Needs network (python.org embeddable zip + PyPI).

  python tools/build_python_bundle.py [--py-version 3.11.9] [--out dist]
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COPY_INTO_ROOT = ("src", "app", "demo_cases", "pyproject.toml", "README.md",
                  # Licence texts travel with the payload: the bundled R is GPL
                  # and NOTICE.md carries the source offer and the inventory.
                  "LICENSE", "NOTICE.md")


def log(msg: str) -> None:
    print(msg, flush=True)


def download(url: str) -> bytes:
    log(f"  downloading {url}")
    with urllib.request.urlopen(url) as r:  # noqa: S310 (trusted python.org/pypa)
        return r.read()


def dir_size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024 ** 2


def build_embeddable_python(pydir: Path, version: str) -> None:
    tag = "".join(version.split(".")[:2])  # 3.11.9 -> "311"
    url = f"https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip"
    zipfile.ZipFile(io.BytesIO(download(url))).extractall(pydir)

    # Enable site so pip and .pth files work; put site-packages on the path.
    pth = pydir / f"python{tag}._pth"
    pth.write_text(f"python{tag}.zip\n.\nLib\\site-packages\n\nimport site\n",
                   encoding="utf-8")

    log("  bootstrapping pip")
    (pydir / "get-pip.py").write_bytes(download("https://bootstrap.pypa.io/get-pip.py"))
    run(pydir, ["get-pip.py", "--no-warn-script-location"])
    (pydir / "get-pip.py").unlink()


def run(pydir: Path, args: list[str]) -> None:
    exe = pydir / "python.exe"
    res = subprocess.run([str(exe), *args], cwd=str(pydir))
    if res.returncode != 0:
        raise SystemExit(f"command failed: {exe} {' '.join(args)}")


def install_deps(pydir: Path) -> None:
    # Install geosurrogate[ui] to pull the exact pinned dependency set, then drop
    # the geosurrogate package itself — the app runs from the copied src/ via the
    # relative .pth, so it must not also live in site-packages (that would put
    # REPO_DIR inside site-packages and hide app/ + demo_cases/).
    log("  installing geosurrogate[ui] to resolve dependencies")
    run(pydir, ["-m", "pip", "install", "--no-warn-script-location",
                "--no-cache-dir", f"{REPO}[ui]"])
    sp = pydir / "Lib" / "site-packages"
    shutil.rmtree(sp / "geosurrogate", ignore_errors=True)
    for meta in sp.glob("geosurrogate-*.dist-info"):
        shutil.rmtree(meta, ignore_errors=True)
    # Relative import path: site-packages -> Lib -> python -> dist(root) -> src
    (sp / "geosurrogate.pth").write_text("..\\..\\..\\src\n", encoding="utf-8")


def prune_python(pydir: Path) -> None:
    """Drop __pycache__ and shipped test suites — safe for a runtime bundle
    (the biggest win: numpy/scipy/pandas ship large tests, and bytecode caches
    regenerate on first import)."""
    for cache in list(pydir.rglob("__pycache__")):
        shutil.rmtree(cache, ignore_errors=True)
    sp = pydir / "Lib" / "site-packages"
    for name in ("tests", "test"):
        for d in list(sp.rglob(name)):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)


def smoke_test(dist: Path) -> None:
    # Prove the bundled Python renders the dashboard against the copied layout.
    script = dist / "_smoketest.py"
    script.write_text(
        "from streamlit.testing.v1 import AppTest\n"
        f"at = AppTest.from_file(r'{dist / 'app' / 'Home.py'}', default_timeout=90)\n"
        "at.run()\n"
        "assert not at.exception, at.exception\n"
        "print('APPTEST_OK')\n", encoding="utf-8")
    exe = dist / "python" / "python.exe"
    res = subprocess.run([str(exe), str(script)], capture_output=True, text=True)
    script.unlink(missing_ok=True)
    if "APPTEST_OK" not in res.stdout:
        raise SystemExit(f"bundle smoke test FAILED:\n{res.stdout}\n{res.stderr}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the Python + geosurrogate bundle.")
    ap.add_argument("--py-version", default="3.11.9")
    ap.add_argument("--out", type=Path, default=REPO / "dist")
    args = ap.parse_args()

    if sys.platform != "win32":
        log("This bundle targets the native Windows product; run it on Windows.")
        return 1

    dist = args.out
    pydir = dist / "python"
    log(f"Bundle root: {dist}")

    # Clean only what this script owns (leave a sibling dist/R intact).
    if pydir.exists():
        shutil.rmtree(pydir)
    for name in (*COPY_INTO_ROOT, "launcher.py"):
        target = dist / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    dist.mkdir(parents=True, exist_ok=True)

    log("Building embeddable Python...")
    build_embeddable_python(pydir, args.py_version)
    log("Installing dependencies...")
    install_deps(pydir)
    log("Pruning caches and test suites...")
    prune_python(pydir)

    log("Copying repo layout into the bundle root...")
    for name in COPY_INTO_ROOT:
        src = REPO / name
        dstp = dist / name
        if src.is_dir():
            shutil.copytree(src, dstp)
        else:
            shutil.copy2(src, dstp)
    # The desktop shortcut runs this; it must sit at the install root, beside
    # python/. It lives in installer/, which is not part of the public repo (the
    # native .exe is distributed by the author), so its absence is not an error:
    # the bundle still runs via `python\python.exe -m streamlit run app\Home.py`.
    launcher = REPO / "installer" / "launcher.py"
    if launcher.exists():
        shutil.copy2(launcher, dist / "launcher.py")
    else:
        log("  (no installer/launcher.py — bundle built without the shortcut entry point)")

    log("Smoke test: rendering the dashboard from the bundle...")
    smoke_test(dist)

    log(f"\nDONE. Python bundle in {pydir} — {dir_size_mb(pydir):.0f} MB")
    log(f"Launch with: {pydir / 'python.exe'} -m streamlit run "
        f"{dist / 'app' / 'Home.py'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
