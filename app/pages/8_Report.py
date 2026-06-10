import io
import zipfile
from pathlib import Path

import streamlit as st

from geosurrogate.ui.common import current_project, init_page, t

ARTIFACTS = [
    ("project.yaml", "Configuration"),
    ("dataset.xlsx", "Training dataset (Excel)"),
    ("dataset.csv", "Training dataset (CSV)"),
    ("events.jsonl", "Run event history"),
    ("validation/loocv_panel.png", "LOOCV panel"),
    ("validation/loocv.csv", "LOOCV data"),
    ("validation/massive_panel.png", "Massive validation panel"),
    ("validation/massive.csv", "Massive validation data"),
    ("validation/ks_curve.png", "K-S convergence curve"),
    ("validation/ks_curve.csv", "K-S curve data"),
    ("exploitation/mcs_histogram.png", "MCS histogram"),
    ("exploitation/mcs_metrics.json", "MCS metrics"),
]

init_page("report.title")
project = current_project()
if project:
    st.caption(t("report.html_soon"))
    st.subheader(t("report.artifacts"))
    for rel, label in ARTIFACTS:
        path = project.root / rel
        if path.exists():
            col1, col2 = st.columns([3, 1])
            col1.write(f"`{rel}` - {label}")
            col2.download_button(t("common.download"), data=path.read_bytes(),
                                 file_name=path.name, key=f"dl_{rel}")

    st.divider()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, _label in ARTIFACTS:
            path = project.root / rel
            if path.exists():
                zf.write(path, arcname=f"{Path(project.root).name}/{rel}")
    st.download_button(t("report.zip"), data=buf.getvalue(),
                       file_name=f"{Path(project.root).name}_results.zip",
                       type="primary")
