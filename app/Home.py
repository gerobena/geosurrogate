"""geosurrogate dashboard - project hub."""

import datetime as dt
import shutil
from pathlib import Path

import pandas as pd
import streamlit as st

from geosurrogate.config import (ALConfig, DoEConfig, ProjectConfig,
                                 ProjectMeta, SolverConfig)
from geosurrogate.project import Project
from geosurrogate.solvers.demo import load_case_config, load_registry
from geosurrogate.ui import wizard
from geosurrogate.ui.common import (RUNS_DIR, current_project, init_page,
                                    list_projects, t)

init_page("app.title")
st.caption(t("app.tagline"))

tab_open, tab_new, tab_fez = st.tabs([t("home.open"), t("home.new_demo"),
                                      t("home.new_fez")])

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
        if st.button(t("home.open_btn"), type="primary", key="open_selected"):
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
    if st.button(t("home.create_btn"), type="primary", key="create_demo"):
        cfg = load_case_config(case_id)
        workdir = RUNS_DIR / f"{case_id}_{dt.datetime.now():%Y%m%d_%H%M%S}"
        Project.create(workdir, cfg)
        st.session_state["project_root"] = str(workdir)
        st.success(t("home.created"))
        st.rerun()

with tab_fez:
    st.caption(t("home.fez_intro"))
    name = st.text_input(t("home.fez_name"), value="")
    uploaded = st.file_uploader(t("home.fez_upload"), type=["fez"], key="fez_file")
    if uploaded is not None:
        staging = RUNS_DIR / "_staging"
        staging.mkdir(parents=True, exist_ok=True)
        staged = staging / uploaded.name
        if (st.session_state.get("fez_path") != str(staged)
                or not staged.exists()):
            staged.write_bytes(uploaded.getvalue())
            st.session_state["fez_path"] = str(staged)
            st.session_state.pop("fez_materials", None)

    staged_path = st.session_state.get("fez_path")
    if staged_path:
        st.caption(f"`{Path(staged_path).name}` "
                   f"({Path(staged_path).stat().st_size / 1e6:.1f} MB)")
        if st.button(t("home.fez_detect"), key="fez_detect"):
            from geosurrogate.solvers.rs2 import (RS2ConnectionError,
                                                  RS2NotAvailable,
                                                  discover_materials)
            try:
                with st.spinner(t("home.fez_detecting")):
                    mats = discover_materials(Path(staged_path))
                st.session_state["fez_materials"] = [
                    {"name": m.name, "current_values": m.current_values}
                    for m in mats]
            except (RS2NotAvailable, RS2ConnectionError, Exception) as e:
                st.error(str(e))

    mats_raw = st.session_state.get("fez_materials")
    if mats_raw:
        st.success(t("home.fez_detected", n=len(mats_raw)))

        class _M:
            def __init__(self, d):
                self.name = d["name"]
                self.current_values = d["current_values"]

        st.markdown(f"**{t('home.fez_editor_title')}**")
        st.caption(t("home.fez_editor_note"))
        base = wizard.editor_rows([_M(d) for d in mats_raw])
        edited = st.data_editor(
            base,
            column_config={
                "include": st.column_config.CheckboxColumn(t("wiz.include")),
                "material": st.column_config.TextColumn(t("wiz.material"),
                                                        disabled=True),
                "property": st.column_config.TextColumn(t("wiz.property"),
                                                        disabled=True),
                "current": st.column_config.NumberColumn(t("wiz.current"),
                                                         disabled=True,
                                                         format="%.2f"),
                "family": st.column_config.SelectboxColumn(
                    t("wiz.family"), options=wizard.FAMILIES),
                "mean": st.column_config.NumberColumn(t("wiz.mean")),
                "std": st.column_config.NumberColumn(t("wiz.std")),
                "low": st.column_config.NumberColumn(t("wiz.low")),
                "high": st.column_config.NumberColumn(t("wiz.high")),
            },
            hide_index=True, width="stretch", key="fez_editor")

        d = int((edited["include"] == True).sum())  # noqa: E712
        if d:
            rec = wizard.recommend_doe(d)
            st.info(t("home.fez_doe", d=d, strategy=rec["strategy"],
                      n=rec["design_size"]))
            c1, c2 = st.columns(2)
            tol = c1.number_input(t("home.fez_tolerance"), min_value=0.0001,
                                  value=0.01, step=0.001, format="%.4f")
            budget = c2.number_input(t("home.fez_budget"), min_value=rec["design_size"],
                                     value=rec["budget"], step=5)

            if st.button(t("home.fez_create"), type="primary", key="fez_create"):
                try:
                    variables = wizard.rows_to_variables(edited)
                except ValueError as e:
                    st.error(str(e))
                else:
                    proj_name = name.strip() or Path(staged_path).stem
                    workdir = RUNS_DIR / (f"{wizard.slug(proj_name)}_"
                                          f"{dt.datetime.now():%Y%m%d_%H%M%S}")
                    model_dir = workdir / "model"
                    model_dir.mkdir(parents=True, exist_ok=True)
                    model_dest = model_dir / Path(staged_path).name
                    shutil.copy2(staged_path, model_dest)
                    cfg = ProjectConfig(
                        project=ProjectMeta(name=proj_name),
                        solver=SolverConfig(type="rs2",
                                            model_file=model_dest.resolve()),
                        variables=variables,
                        doe=DoEConfig(strategy=rec["strategy"],
                                      n_lhs=max(rec["n_lhs"], 4),
                                      n_pem=max(rec["n_pem"], 4)),
                        active_learning=ALConfig(tolerance=float(tol),
                                                 budget_total_sims=int(budget)),
                    )
                    Project.create(workdir, cfg, exist_ok=True)
                    st.session_state["project_root"] = str(workdir)
                    for k in ("fez_materials", "fez_path"):
                        st.session_state.pop(k, None)
                    st.success(t("home.fez_created"))
                    st.rerun()

project = st.session_state.get("project_root")
if project:
    st.divider()
    p = current_project()
    if p:
        st.write(f"**{p.config.project.name}** - {p.config.dims}D - "
                 f"solver `{p.config.solver.type}`")
