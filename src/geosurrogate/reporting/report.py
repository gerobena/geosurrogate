"""Self-contained HTML report: configuration, training summary, validation
and exploitation results with embedded figures. One file, no external assets."""

from __future__ import annotations

import base64
import datetime as dt
import json
from pathlib import Path

from .. import __version__
from ..project import Project

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;margin:40px auto;max-width:1100px;color:#222}
h1{border-bottom:3px solid #1f3552;padding-bottom:8px}h2{color:#1f3552;margin-top:36px}
table{border-collapse:collapse;margin:12px 0}td,th{border:1px solid #ccc;padding:6px 12px;text-align:left}
th{background:#f0f3f7}img{max-width:100%;border:1px solid #ddd;margin:8px 0}
.metric{display:inline-block;background:#f0f3f7;border-radius:8px;padding:10px 18px;margin:4px}
.metric b{display:block;font-size:1.3em;color:#1f3552}.note{color:#666;font-size:.9em}
footer{margin-top:40px;color:#888;font-size:.85em;border-top:1px solid #ddd;padding-top:10px}
"""


def _img(path: Path) -> str:
    if not path.exists():
        return ""
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{b64}">'


def _metrics(items: dict[str, str]) -> str:
    return "".join(f'<div class="metric"><b>{v}</b>{k}</div>' for k, v in items.items())


def _load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def generate_report(project: Project) -> Path:
    cfg = project.config
    state = project.read_state()
    ds = project.load_dataset()
    ok = ds[ds["status"] == "ok"]
    val, exp = project.root / "validation", project.root / "exploitation"

    parts: list[str] = []
    parts.append(f"<h1>{cfg.project.name}</h1>")
    parts.append(f'<p class="note">geosurrogate v{__version__} - generated '
                 f"{dt.datetime.now():%Y-%m-%d %H:%M} - project: {project.root}</p>")

    # --- configuration ----------------------------------------------------
    parts.append("<h2>1. Configuration</h2>")
    rows = "".join(
        f"<tr><td>{v.id}</td><td>{v.material}</td><td>{v.property}</td>"
        f"<td>{v.training_bounds[0]:g} - {v.training_bounds[1]:g}</td>"
        f"<td>{v.distribution.family}</td></tr>" for v in cfg.variables)
    parts.append(f"<p>Solver: <b>{cfg.solver.type}</b> | dimensionality: "
                 f"<b>{cfg.dims}D</b> | DoE: <b>{cfg.doe.strategy}</b> | "
                 f"AL tolerance: <b>{cfg.active_learning.tolerance:g}</b> | "
                 f"surrogate: <b>{cfg.surrogate.engine}</b> (nmcmc "
                 f"{cfg.surrogate.mcmc.nmcmc})</p>")
    parts.append("<table><tr><th>variable</th><th>material</th><th>property</th>"
                 f"<th>training box</th><th>distribution</th></tr>{rows}</table>")

    # --- training ----------------------------------------------------------
    parts.append("<h2>2. Training summary</h2>")
    items = {"FEM simulations (ok)": str(len(ok)),
             "stop reason": str(state.get("stop_reason", "-")),
             "AL iterations": str(state.get("iteration", "-"))}
    if state.get("error_max") is not None:
        items["last surface error_max"] = f"{state['error_max']:.5f}"
    if len(ok):
        items["SRF range (training)"] = f"{ok['srf'].min():.2f} - {ok['srf'].max():.2f}"
    parts.append(_metrics(items))

    # --- validation ---------------------------------------------------------
    loocv = _load(val / "loocv_metrics.json")
    massive = _load(val / "massive_metrics.json")
    ks = _load(val / "ks_metrics.json")
    if any([loocv, massive, ks]):
        parts.append("<h2>3. Validation</h2>")
    if loocv:
        parts.append("<h3>3.1 Leave-One-Out Cross-Validation</h3>")
        parts.append(_metrics({"R<sup>2</sup>": f"{loocv['r2']:.4f}",
                               "RMSE": f"{loocv['rmse']:.4f}",
                               "coverage &plusmn;2&sigma;": f"{100 * loocv['coverage_2sd']:.0f}%",
                               "n": str(loocv["n"])}))
        parts.append(_img(val / "loocv_panel.png"))
    if massive:
        verdict = ("H0 rejected at &alpha; = 0.05" if massive["ks_h0_rejected_at_005"]
                   else "H0 not rejected at &alpha; = 0.05")
        parts.append("<h3>3.2 Massive validation (independent FEM results)</h3>")
        parts.append(_metrics({"R<sup>2</sup>": f"{massive['r2']:.4f}",
                               "RMSE": f"{massive['rmse']:.4f}",
                               "K-S D": f"{massive['ks_D']:.4f}",
                               "p-value": f"{massive['ks_pvalue']:.3f}",
                               "n test": str(massive["n_test"])}))
        parts.append(f'<p class="note">Two-sample Kolmogorov-Smirnov: {verdict}. '
                     "The test never demonstrates equality of distributions; "
                     "convergence is argued primarily with D.</p>")
        parts.append(_img(val / "massive_panel.png"))
    if ks:
        parts.append("<h3>3.3 Distributional convergence (K-S vs n)</h3>")
        parts.append(_metrics({"final D": f"{ks['final_D']:.4f}",
                               "final p-value": f"{ks['final_pvalue']:.3f}",
                               "n range": f"{ks['n_min']} - {ks['n_max']}"}))
        parts.append(_img(val / "ks_curve.png"))

    # --- exploitation --------------------------------------------------------
    mcs = _load(exp / "mcs_metrics.json")
    if mcs:
        parts.append("<h2>4. Exploitation - Monte Carlo Simulation</h2>")
        parts.append(_metrics({
            "PoF = P[SRF &lt; " + f"{mcs['failure_threshold']:g}]": f"{mcs['pof']:.4g}",
            "95% CI": f"{mcs['pof_ci95'][0]:.3g} - {mcs['pof_ci95'][1]:.3g}",
            "SRF mean": f"{mcs['srf_mean']:.3f}",
            "SRF std": f"{mcs['srf_std']:.3f}",
            "MCS samples": f"{mcs['n_samples']:,}"}))
        if mcs.get("pof_note"):
            parts.append(f'<p class="note">{mcs["pof_note"]}</p>')
        parts.append(_img(exp / "mcs_histogram.png"))

    parts.append("<footer>Surrogate: Gaussian Process (deepgp, MCMC) trained by "
                 "active learning (ALC). Every FEM value originates from RS2 "
                 "finite-element analyses.</footer>")

    html = (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{cfg.project.name}</title><style>{CSS}</style></head>"
            f"<body>{''.join(parts)}</body></html>")
    out_dir = project.root / "report"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"report_{dt.datetime.now():%Y%m%d_%H%M%S}.html"
    out.write_text(html, encoding="utf-8")
    project.append_event("report_generated", file=str(out))
    return out
