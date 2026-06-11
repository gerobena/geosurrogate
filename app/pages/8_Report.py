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
    if st.button(t("report.generate"), type="primary"):
        from geosurrogate.reporting.report import generate_report

        path = generate_report(project)
        st.success(str(path))

    reports = sorted((project.root / "report").glob("report_*.html"), reverse=True)
    for r in reports[:5]:
        st.download_button(f"{t('common.download')} {r.name}", data=r.read_bytes(),
                           file_name=r.name, key=f"rep_{r.name}")

    st.divider()
    st.subheader(t("report.artifacts"))
    extra = [(f"validation/{p.name}", "Independent FEM testset")
             for p in (project.root / "validation").glob("testset_*.xlsx")
             if "_inputs" not in p.name]
    for rel, label in ARTIFACTS + extra:
        path = project.root / rel
        if path.exists():
            col1, col2 = st.columns([3, 1])
            col1.write(f"`{rel}` - {label}")
            col2.download_button(t("common.download"), data=path.read_bytes(),
                                 file_name=path.name, key=f"dl_{rel}")

    st.divider()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, _label in ARTIFACTS + extra:
            path = project.root / rel
            if path.exists():
                zf.write(path, arcname=f"{Path(project.root).name}/{rel}")
        for r in reports[:1]:
            zf.write(r, arcname=f"{Path(project.root).name}/report/{r.name}")
    st.download_button(t("report.zip"), data=buf.getvalue(),
                       file_name=f"{Path(project.root).name}_results.zip",
                       type="primary")
