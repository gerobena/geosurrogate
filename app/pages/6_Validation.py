import datetime as dt

import pandas as pd
import streamlit as st

from geosurrogate.ui.common import (current_project, init_page, launch_cli,
                                    load_json, running_stage, show_image,
                                    stage_progress_bar, t, tail_file)

init_page("val.title")
project = current_project()
if project:
    cfg = project.config
    is_demo = cfg.solver.type == "demo"
    val_dir = project.root / "validation"
    val_dir.mkdir(exist_ok=True)

    def _running(progress_file) -> dict | None:
        data = load_json(progress_file)
        if not data:
            return None
        try:
            age = (dt.datetime.now()
                   - dt.datetime.fromisoformat(data["ts"])).total_seconds()
        except (KeyError, ValueError):
            age = 0
        return data if age < 240 else None

    def _progress_bar(data: dict) -> None:
        st.progress(min(data["done"] / max(data["total"], 1), 1.0),
                    text=t("val.in_progress", done=data["done"], total=data["total"]))

    @st.fragment(run_every=3)
    def live_validation():
        # =====================================================================
        # 1. INTERNAL VALIDATION - only the training data is needed
        # =====================================================================
        st.subheader(t("val.sec_internal"))
        st.caption(t("val.sec_internal_note"))
        with st.container(border=True):
            st.markdown(f"**{t('val.loocv')}**")
            prog = _running(val_dir / "loocv_progress.json")
            m = load_json(val_dir / "loocv_metrics.json")
            if m:
                cols = st.columns(4)
                cols[0].metric("R2", f"{m['r2']:.4f}")
                cols[1].metric("RMSE", f"{m['rmse']:.4f}")
                cols[2].metric("Coverage +/-2sd", f"{100 * m['coverage_2sd']:.0f}%")
                cols[3].metric("n", m["n"])
                show_image(val_dir / "loocv_panel.png")
            if prog:
                _progress_bar(prog)
            elif not m:
                st.write(t("common.not_available"))
            if st.button(t("val.run_loocv"), key="run_loocv", disabled=prog is not None):
                launch_cli(project, ["validate", str(project.root), "--loocv"],
                           "validate")
                st.info(t("val.launched"))

        # =====================================================================
        # 2. INDEPENDENT VALIDATION - requires FEM results the model never saw
        # =====================================================================
        st.subheader(t("val.sec_independent"))
        st.caption(t("val.sec_independent_note"))

        # --- validation dataset source ---------------------------------------
        source_args: list[str] | None = None
        with st.container(border=True):
            st.markdown(f"**{t('val.dataset')}**")
            testsets = sorted(p for p in val_dir.glob("testset_*.xlsx")
                              if "_inputs" not in p.name)
            options: list[str] = []
            if is_demo:
                from geosurrogate.solvers.demo import demo_cases_dir
                lookup = pd.read_csv(demo_cases_dir() / cfg.solver.demo_case
                                     / "lookup.csv")
                n_ok = int((project.load_dataset()["status"] == "ok").sum())
                pool_label = t("val.dataset_pool", n=max(len(lookup) - n_ok, 0))
                options.append(pool_label)
            options += [str(p) for p in testsets]
            if options:
                sel = st.selectbox(t("val.testset_pick"), options=options,
                                   key="indep_source")
                source_args = (["--use-pool"] if is_demo and sel == options[0]
                               else ["--test-xlsx", sel])
            else:
                st.warning(t("val.dataset_none"))

            up_col, gen_col = st.columns(2)
            with up_col:
                uploaded = st.file_uploader(t("val.upload"), type=["xlsx", "csv"],
                                            key="upload_testset")
                if uploaded is not None:
                    import io
                    raw = (pd.read_csv(io.BytesIO(uploaded.getvalue()))
                           if uploaded.name.lower().endswith(".csv")
                           else pd.read_excel(io.BytesIO(uploaded.getvalue())))
                    missing = [c for c in (*cfg.var_ids, "srf")
                               if c not in raw.columns]
                    if missing:
                        st.error(t("val.upload_bad", cols=", ".join(missing)))
                    else:
                        stem = uploaded.name.rsplit(".", 1)[0]
                        dest = val_dir / f"testset_upload_{stem}.xlsx"
                        if not dest.exists():
                            raw[[*cfg.var_ids, "srf"]].dropna().to_excel(
                                dest, index=False)
                            st.success(t("val.upload_ok", n=len(raw),
                                         name=dest.name))
            with gen_col:
                if not is_demo:
                    st.caption(t("val.testset_note"))
                    for p in sorted(val_dir.glob("testset_*_partial.csv")):
                        done = len(pd.read_csv(p))
                        st.progress(min(done / 80, 1.0),
                                    text=t("val.testset_progress", done=done,
                                           name=p.name))
                    n = st.number_input("n", min_value=10, max_value=500, value=80)
                    if st.button(t("val.testset_run"), key="run_testset"):
                        launch_cli(project, ["testset", str(project.root),
                                             "--n", str(int(n))], "testset")
                        st.info(t("val.launched"))
                    log = tail_file(project.root / "log" / "testset.out", 4)
                    if log:
                        st.code(log)

        # --- massive validation -----------------------------------------------
        with st.container(border=True):
            st.markdown(f"**{t('val.massive')}**")
            mprog = running_stage(val_dir / "massive_progress.json", max_age_s=1800)
            m = load_json(val_dir / "massive_metrics.json")
            if m:
                verdict = t("val.reject_h0") if m["ks_h0_rejected_at_005"] \
                    else t("val.no_reject_h0")
                cols = st.columns(4)
                cols[0].metric("R2", f"{m['r2']:.4f}")
                cols[1].metric("RMSE", f"{m['rmse']:.4f}")
                cols[2].metric("K-S D", f"{m['ks_D']:.4f}")
                cols[3].metric("p-value", f"{m['ks_pvalue']:.3f}")
                st.caption(verdict)
                show_image(val_dir / "massive_panel.png")
            if mprog:
                stage_progress_bar(mprog)
            elif not m:
                st.write(t("common.not_available"))
            if st.button(t("val.run_massive"), key="run_massive",
                         disabled=(source_args is None or mprog is not None)):
                launch_cli(project, ["validate", str(project.root), "--no-loocv",
                                     "--massive", *source_args], "validate")
                st.info(t("val.launched"))

        # --- K-S curve ----------------------------------------------------------
        with st.container(border=True):
            st.markdown(f"**{t('val.ks')}**")
            prog = _running(val_dir / "ks_progress.json")
            m = load_json(val_dir / "ks_metrics.json")
            if m:
                cols = st.columns(3)
                cols[0].metric("final D", f"{m['final_D']:.4f}")
                cols[1].metric("final p-value", f"{m['final_pvalue']:.3f}")
                cols[2].metric("n range", f"{m['n_min']} - {m['n_max']}")
                show_image(val_dir / "ks_curve.png")
            if prog:
                _progress_bar(prog)
            elif not m:
                st.write(t("common.not_available"))
            if st.button(t("val.run_ks"), key="run_ks",
                         disabled=(source_args is None or prog is not None)):
                launch_cli(project, ["validate", str(project.root), "--no-loocv",
                                     "--ks", *source_args], "validate")
                st.info(t("val.launched"))

        log = tail_file(project.root / "log" / "validate.out")
        if log:
            with st.expander(t("val.log")):
                st.code(log)

    live_validation()
