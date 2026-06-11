"""Shared helpers for the Streamlit app: i18n, project session, launchers.

Lives inside the installed package (not in app/) so that pages import it
reliably under both `streamlit run` and Streamlit's AppTest harness. Core
modules never import this (streamlit is an optional dependency).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from ..project import Project

REPO_DIR = Path(__file__).resolve().parents[3]
APP_DIR = REPO_DIR / "app"
RUNS_DIR = REPO_DIR / "runs"


# --- i18n -----------------------------------------------------------------
@st.cache_data
def _load_lang(lang: str) -> dict:
    path = APP_DIR / "i18n" / f"{lang}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def t(key: str, **fmt) -> str:
    lang = st.session_state.get("lang", "en")
    table = _load_lang(lang)
    text = table.get(key) or _load_lang("en").get(key) or key
    return text.format(**fmt) if fmt else text


# --- page scaffolding -------------------------------------------------------
def init_page(title_key: str) -> None:
    st.set_page_config(page_title=f"{t(title_key)} - geosurrogate", layout="wide")
    with st.sidebar:
        st.selectbox(t("common.language"), options=["en", "es"], key="lang",
                     format_func=lambda x: {"en": "English", "es": "Español"}[x])
        root = st.session_state.get("project_root")
        st.caption(f"{t('common.project')}: " + (str(root) if root else "-"))
    st.title(t(title_key))


def current_project() -> Project | None:
    root = st.session_state.get("project_root")
    if not root:
        st.info(t("common.no_project"))
        return None
    try:
        return Project.open(root)
    except FileNotFoundError:
        st.error(f"Project not found: {root}")
        return None


def list_projects() -> list[Path]:
    if not RUNS_DIR.exists():
        return []
    return sorted([p for p in RUNS_DIR.iterdir()
                   if p.is_dir() and (p / "project.yaml").exists()])


# --- data loaders -----------------------------------------------------------
def load_events(project: Project) -> pd.DataFrame:
    if not project.events_path.exists():
        return pd.DataFrame()
    rows = [json.loads(line) for line in
            project.events_path.read_text(encoding="utf-8").splitlines() if line]
    return pd.DataFrame(rows)


def load_json(path: Path) -> dict | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def show_image(path: Path) -> bool:
    if path.exists():
        st.image(str(path), width="stretch")
        return True
    return False


def tail_file(path: Path, n: int = 15) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:])


# --- stage-based progress (single long R call: MCS, massive validation) ------
STAGE_FRACTION = {"sampling": 0.08, "predicting": 0.55, "finalizing": 0.92}


def running_stage(path: Path, max_age_s: int = 3600) -> dict | None:
    """Stage-progress data of an in-flight long analysis, or None.

    The timestamp cannot tick during the long R call, so staleness is judged
    from the start time with a generous cap instead of the last update.
    """
    import datetime as dt

    data = load_json(path)
    if not data:
        return None
    try:
        started = dt.datetime.fromisoformat(data["started"])
    except (KeyError, ValueError):
        return None
    elapsed = (dt.datetime.now() - started).total_seconds()
    if elapsed > max_age_s:
        return None
    data["elapsed"] = elapsed
    return data


def stage_progress_bar(data: dict) -> None:
    mins, secs = divmod(int(data.get("elapsed", 0)), 60)
    stage = data.get("stage", "predicting")
    st.progress(STAGE_FRACTION.get(stage, 0.5),
                text=t("common.running_stage", stage=t(f"stage.{stage}"),
                       elapsed=f"{mins:d}:{secs:02d}"))


# --- background launchers ---------------------------------------------------
def launch_cli(project: Project, args: list[str], tag: str) -> int:
    """Run a geosurrogate CLI command detached; output goes to log/<tag>.out."""
    log_path = project.root / "log" / f"{tag}.out"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "a", encoding="utf-8")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen([sys.executable, "-m", "geosurrogate.cli", *args],
                            stdout=log, stderr=subprocess.STDOUT,
                            creationflags=flags, cwd=str(REPO_DIR))
    return proc.pid
