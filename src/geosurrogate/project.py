"""Analysis project: a self-contained folder with config, state, events and dataset."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import pandas as pd

from .config import ProjectConfig

DATASET_META_COLS = ["case_id", "srf", "predicted_srf", "status", "source", "elapsed_s", "ts"]


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class Project:
    def __init__(self, root: Path, config: ProjectConfig):
        # Absolute root: derived paths get handed to external processes (RS2,
        # Rscript) that run with their own working directories.
        self.root = Path(root).resolve()
        self.config = config

    # --- paths ---------------------------------------------------------
    @property
    def config_path(self) -> Path:
        return self.root / "project.yaml"

    @property
    def dataset_path(self) -> Path:
        return self.root / "dataset.csv"

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    @property
    def events_path(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def control_path(self) -> Path:
        return self.root / "control.json"

    @property
    def log_path(self) -> Path:
        return self.root / "log" / "run.log"

    @property
    def fem_dir(self) -> Path:
        return self.root / "fem"

    @property
    def surrogate_dir(self) -> Path:
        return self.root / "surrogate"

    # --- lifecycle -----------------------------------------------------
    @classmethod
    def create(cls, root: Path | str, config: ProjectConfig, exist_ok: bool = False) -> "Project":
        root = Path(root)
        if root.exists() and any(root.iterdir()) and not exist_ok:
            raise FileExistsError(f"project folder already exists and is not empty: {root}")
        for sub in ("log", "fem", "surrogate"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        p = cls(root, config)
        config.to_yaml(p.config_path)
        cols = ["case_id", *config.var_ids, "srf", "predicted_srf", "status", "source", "elapsed_s", "ts"]
        pd.DataFrame(columns=cols).to_csv(p.dataset_path, index=False)
        p.write_state(phase="created", status="idle", iteration=0, n_samples=0,
                      budget_total=config.active_learning.budget_total_sims, started_at=_now())
        return p

    @classmethod
    def open(cls, root: Path | str) -> "Project":
        root = Path(root)
        cfg_path = root / "project.yaml"
        if not cfg_path.exists():
            raise FileNotFoundError(f"not a geosurrogate project (missing project.yaml): {root}")
        return cls(root, ProjectConfig.from_yaml(cfg_path))

    # --- state / events / control --------------------------------------
    def read_state(self) -> dict:
        if not self.state_path.exists():
            return {}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def write_state(self, **updates) -> dict:
        state = self.read_state()
        state.update(updates)
        state["updated_at"] = _now()
        _atomic_write_text(self.state_path, json.dumps(state, indent=1))
        return state

    def append_event(self, event_type: str, **payload) -> None:
        line = json.dumps({"ts": _now(), "type": event_type, **payload})
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def pause_requested(self) -> bool:
        if not self.control_path.exists():
            return False
        try:
            req = json.loads(self.control_path.read_text(encoding="utf-8")).get("request")
        except (json.JSONDecodeError, OSError):
            return False
        return req in ("pause", "stop")

    def clear_control(self) -> None:
        self.control_path.unlink(missing_ok=True)

    def log(self, msg: str) -> None:
        line = f"[{_now()}] {msg}"
        print(line, flush=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # --- dataset --------------------------------------------------------
    def load_dataset(self) -> pd.DataFrame:
        return pd.read_csv(self.dataset_path)

    def append_case(self, row: dict) -> pd.DataFrame:
        df = self.load_dataset()
        row = {**row, "ts": _now()}
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        tmp = self.dataset_path.with_suffix(".csv.tmp")
        df.to_csv(tmp, index=False)
        os.replace(tmp, self.dataset_path)
        return df

    def export_xlsx(self) -> Path:
        out = self.root / "dataset.xlsx"
        self.load_dataset().to_excel(out, index=False)
        return out
