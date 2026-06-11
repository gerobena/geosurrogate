import datetime as dt

import pandas as pd
import streamlit as st

from geosurrogate.ui.common import (current_project, init_page, launch_cli,
                                    load_json, show_image, t, tail_file)

init_page("val.title")
project = current_project()
if project:
    cfg = project.config
    is_demo = cfg.solver.type == "demo"
    val_dir = project.root / "validation"
    st.caption(t("val.cost_note"))

    def _running(progress_file) -> dict | None:
        """Progress data of an in-flight analysis, or None if absent/stale."""
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
        # --- independent testset (real-solver projects) ----------------------
        testsets = sorted(p for p in val_dir.glob("testset_*.xlsx")
                          if "_inputs" not in p.name)
        if not is_demo:
            with st.expander(t("val.testset"), expanded=not testsets):
                st.caption(t("val.testset_note"))
                for p in sorted(val_dir.glob("testset_*_partial.csv")):
                    done = len(pd.read_csv(p))
                    st.progress(min(done / 80, 1.0),
                                text=t("val.testset_progress", done=done, name=p.name))
                n = st.number_input("n", min_value=10, max_value=500, value=80)
                if st.button(t("val.testset_run")):
                    launch_cli(project, ["testset", str(project.root),
                                         "--n", str(int(n))], "testset")
                    st.info(t("val.launched"))
                log = tail_file(project.root / "log" / "testset.out", 6)
                if log:
                    st.code(log)

        def _test_source(key: str) -> list[str]:
            if is_demo:
                return ["--use-pool"]
            if testsets:
                sel = st.selectbox(t("val.testset_pick"),
                                   options=[str(p) for p in testsets], key=key)
                return ["--test-xlsx", sel]
            manual = st.text_input(t("val.testset_manual"), key=key + "_manual")
            return ["--test-xlsx", manual or ""]

        # --- LOOCV ------------------------------------------------------------
        with st.expander(t("val.loocv"), expanded=True):
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
            if st.button(t("val.run_loocv"), disabled=prog is not None):
                launch_cli(project, ["validate", str(project.root), "--loocv"],
                           "validate")
                st.info(t("val.launched"))

        # --- massive ------------------------------------------------------------
        with st.expander(t("val.massive")):
            st.caption(t("val.need_test"))
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
            else:
                st.write(t("common.not_available"))
            src = _test_source("massive_src")
            if st.button(t("val.run_massive")):
                launch_cli(project, ["validate", str(project.root), "--no-loocv",
                                     "--massive", *src], "validate")
                st.info(t("val.launched"))

        # --- K-S curve ----------------------------------------------------------
        with st.expander(t("val.ks")):
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
            src = _test_source("ks_src")
            if st.button(t("val.run_ks"), disabled=prog is not None):
                launch_cli(project, ["validate", str(project.root), "--no-loocv",
                                     "--ks", *src], "validate")
                st.info(t("val.launched"))

        log = tail_file(project.root / "log" / "validate.out")
        if log:
            with st.expander(t("val.log")):
                st.code(log)

    live_validation()
