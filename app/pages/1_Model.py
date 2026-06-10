import pandas as pd
import streamlit as st

from geosurrogate.ui.common import current_project, init_page, t
from geosurrogate.solvers.demo import demo_cases_dir, load_registry

init_page("model.title")
project = current_project()
if project:
    cfg = project.config
    c1, c2, c3 = st.columns(3)
    c1.metric(t("model.solver"), cfg.solver.type.upper())
    c2.metric(t("vars.dims"), f"{cfg.dims}D")
    c3.metric("DoE", cfg.doe.strategy)

    if cfg.solver.type == "demo":
        st.info(t("model.demo_info"))
        case_id = cfg.solver.demo_case
        meta = (load_registry().get("cases") or {}).get(case_id, {})
        lookup = pd.read_csv(demo_cases_dir() / case_id / "lookup.csv")
        c1, c2, c3 = st.columns(3)
        c1.metric(t("model.pool_points"), len(lookup))
        c2.metric(t("model.srf_range"),
                  f"{lookup['srf'].min():.2f} - {lookup['srf'].max():.2f}")
        c3.metric("Caso", meta.get("title", case_id))
        st.caption(f"Source: {meta.get('source', '-')}")
    else:
        st.info(t("model.rs2_info"))
        st.code(f"geosurrogate check {project.root} --simulate", language="powershell")
        st.write(f"Model file: `{cfg.solver.model_file}`")
        st.write(f"Ports: modeler {cfg.solver.ports.modeler} / "
                 f"interpreter {cfg.solver.ports.interpreter}")

    st.caption(t("model.geometry_soon"))
    with st.expander(t("common.config")):
        st.code(project.config_path.read_text(encoding="utf-8"), language="yaml")
