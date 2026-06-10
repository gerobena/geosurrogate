"""geosurrogate dashboard - project hub."""

import datetime as dt

import pandas as pd
import streamlit as st

from geosurrogate.ui.common import RUNS_DIR, current_project, init_page, list_projects, t
from geosurrogate.project import Project
from geosurrogate.solvers.demo import load_case_config, load_registry

init_page("app.title")
st.caption(t("app.tagline"))

tab_open, tab_new = st.tabs([t("home.open"), t("home.new_demo")])

with tab_open:
    projects = list_projects()
    if projects:
        st.subheader(t("home.existing"))
        rows = []
        for p in projects:
            try:
                state = Project.open(p).read_state()
            except Exception:
                state = {}
            rows.append({"project": p.name,
                         "phase": state.get("phase", "-"),
                         "status": state.get("status", "-"),
                         "sims": state.get("n_samples", "-"),
                         "updated": state.get("updated_at", "-")})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        choice = st.selectbox(t("common.project"), options=[p.name for p in projects])
        if st.button(t("home.open_btn"), type="primary"):
            st.session_state["project_root"] = str(RUNS_DIR / choice)
            st.rerun()
    else:
        st.info(t("home.none_found"))

    manual = st.text_input(t("home.path_label"))
    if manual:
        st.session_state["project_root"] = manual
        st.rerun()

with tab_new:
    registry = load_registry()
    cases = registry.get("cases") or {}
    case_id = st.selectbox(
        t("home.demo_case"), options=list(cases),
        format_func=lambda c: f"{c} - {cases[c].get('title')} "
                              f"({cases[c].get('dims')}D, pool {cases[c].get('points')})")
    if st.button(t("home.create_btn"), type="primary"):
        cfg = load_case_config(case_id)
        workdir = RUNS_DIR / f"{case_id}_{dt.datetime.now():%Y%m%d_%H%M%S}"
        Project.create(workdir, cfg)
        st.session_state["project_root"] = str(workdir)
        st.success(t("home.created"))
        st.rerun()

project = st.session_state.get("project_root")
if project:
    st.divider()
    p = current_project()
    if p:
        st.write(f"**{p.config.project.name}** - {p.config.dims}D - "
                 f"solver `{p.config.solver.type}`")
