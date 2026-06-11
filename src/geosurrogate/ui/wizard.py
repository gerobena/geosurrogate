"""From-zero wizard logic: turn discovered FEM materials into an editable
variable table and back into a validated project configuration.

Pure pandas/pydantic logic (no streamlit) so it is unit-testable; the Home
page renders it with st.data_editor.
"""

from __future__ import annotations

import re

import pandas as pd

from ..config import Distribution, VariableSpec

PROPERTIES = [("cohesion", "coh"), ("friction_angle", "phi")]
FAMILIES = ["normal", "lognormal", "uniform"]


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "mat"


def editor_rows(materials: list) -> pd.DataFrame:
    """One editable row per material x property, with sensible defaults:
    mean = the model's current value, std = 10% of |mean| (>= 0.5),
    box = mean +/- 3 std (cohesion floored at 0)."""
    rows = []
    for mat in materials:
        current = getattr(mat, "current_values", None) or {}
        for prop, _short in PROPERTIES:
            cur = float(current.get(f"peak_{prop}", 0.0))
            std = max(0.1 * abs(cur), 0.5)
            low = cur - 3 * std
            if prop == "cohesion":
                low = max(low, 0.0)
            rows.append({
                "include": False,
                "material": getattr(mat, "name", str(mat)),
                "property": prop,
                "current": cur,
                "family": "normal",
                "mean": cur,
                "std": round(std, 3),
                "low": round(low, 3),
                "high": round(cur + 3 * std, 3),
            })
    return pd.DataFrame(rows)


def rows_to_variables(df: pd.DataFrame) -> list[VariableSpec]:
    """Selected editor rows -> validated VariableSpec list. Raises ValueError
    with a readable message on the first invalid row."""
    short = dict(PROPERTIES)
    out: list[VariableSpec] = []
    for _, row in df[df["include"] == True].iterrows():  # noqa: E712
        mat, prop = str(row["material"]), str(row["property"])
        low, high = float(row["low"]), float(row["high"])
        if not low < high:
            raise ValueError(f"{mat}/{prop}: low must be < high")
        family = str(row["family"])
        try:
            if family == "uniform":
                dist = Distribution(family="uniform", low=low, high=high)
            else:
                dist = Distribution(family=family, mean=float(row["mean"]),
                                    std=float(row["std"]), truncate=(low, high))
        except Exception as e:
            raise ValueError(f"{mat}/{prop}: {e}") from e
        out.append(VariableSpec(
            id=f"{short[prop]}_{slug(mat)}", material=mat, property=prop,
            training_bounds=(low, high), distribution=dist))
    if not out:
        raise ValueError("select at least one variable")
    ids = [v.id for v in out]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate material/property selections")
    return out


def recommend_doe(d: int) -> dict:
    """DoE strategy by dimensionality (the TFM rule): full factorial for
    D <= 3, hybrid LHS+PEM beyond. Budget leaves room for active learning."""
    if d <= 3:
        n0 = 3 ** d
        return {"strategy": "factorial_3", "n_lhs": 0, "n_pem": 0,
                "design_size": n0, "budget": n0 + 30}
    n_lhs, n_pem = 10 * d, min(2 ** d, 40)
    return {"strategy": "hybrid_lhs_pem", "n_lhs": n_lhs, "n_pem": n_pem,
            "design_size": n_lhs + n_pem, "budget": n_lhs + n_pem + 30}
