"""One-off packaging of demo case lookup tables from TFM result files.

Reads the TFM workspace READ-ONLY and writes demo_cases/<id>/lookup.csv.
Provenance is recorded here on purpose: this script *is* the documentation
of where every demo number comes from.

Run:  .venv/Scripts/python tools/build_demo_cases.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TFM = Path(r"G:\TFM_GeovannyBenavides\RS2Scripting_VSC")
REPO = Path(__file__).resolve().parents[1]

CASES = {
    "slope_2d": {
        "sources": [
            (TFM / "Prueba_Geometria_3" / "Reporte_SRF_Final.xlsx", "train"),
            (TFM / "LHS_500_Geometria_3.xlsx", "validation"),
        ],
        "columns": {"Cohesion": "cohesion", "FrictionAngle": "friction_angle"},
    },
    "embankment_4d": {
        "sources": [
            (TFM / "Prueba_Geometria_5" / "Reporte_SRF_Final.xlsx", "train"),
            (TFM / "LHS_500_Geometria_5.xlsx", "validation"),
        ],
        "columns": {"Coh_Mat1": "coh_m1", "Phi_Mat1": "phi_m1",
                    "Coh_Mat2": "coh_m2", "Phi_Mat2": "phi_m2"},
    },
}


def build(case_id: str, spec: dict) -> None:
    frames = []
    for path, origin in spec["sources"]:
        df = pd.read_excel(path)
        df = df.rename(columns=spec["columns"])
        keep = list(spec["columns"].values())
        df = df[keep + ["Critical_SRF"]].rename(columns={"Critical_SRF": "srf"})
        df["origin"] = origin
        frames.append(df)
        print(f"  {path.name}: {len(df)} rows")
    full = pd.concat(frames, ignore_index=True)
    full["srf"] = pd.to_numeric(full["srf"], errors="coerce")
    n0 = len(full)
    full = full.dropna(subset=["srf"]).drop_duplicates(subset=keep).reset_index(drop=True)
    if len(full) != n0:
        print(f"  dropped {n0 - len(full)} invalid/duplicate rows")
    out = REPO / "demo_cases" / case_id / "lookup.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    full.to_csv(out, index=False)
    print(f"  -> {out} ({len(full)} pool points, "
          f"SRF range {full['srf'].min():.2f}-{full['srf'].max():.2f})")


if __name__ == "__main__":
    for case_id, spec in CASES.items():
        print(f"Building {case_id}")
        build(case_id, spec)
