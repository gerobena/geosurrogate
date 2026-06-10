import streamlit as st

from geosurrogate.ui.common import (current_project, init_page, launch_cli, load_json,
                    show_image, t, tail_file)

init_page("val.title")
project = current_project()
if project:
    cfg = project.config
    is_demo = cfg.solver.type == "demo"
    val_dir = project.root / "validation"
    st.caption(t("val.cost_note"))

    with st.expander(t("val.loocv"), expanded=True):
        m = load_json(val_dir / "loocv_metrics.json")
        if m:
            cols = st.columns(4)
            cols[0].metric("R2", f"{m['r2']:.4f}")
            cols[1].metric("RMSE", f"{m['rmse']:.4f}")
            cols[2].metric("Coverage +/-2sd", f"{100 * m['coverage_2sd']:.0f}%")
            cols[3].metric("n", m["n"])
            show_image(val_dir / "loocv_panel.png")
        else:
            st.write(t("common.not_available"))
        if st.button(t("val.run_loocv")):
            launch_cli(project, ["validate", str(project.root), "--loocv"], "validate")
            st.info(t("val.launched"))

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
        test_path = None if is_demo else st.text_input("FEM results file (.xlsx/.csv)",
                                                       key="massive_test")
        if st.button(t("val.run_massive")):
            args = ["validate", str(project.root), "--no-loocv", "--massive"]
            args += ["--use-pool"] if is_demo else ["--test-xlsx", test_path or ""]
            launch_cli(project, args, "validate")
            st.info(t("val.launched"))

    with st.expander(t("val.ks")):
        m = load_json(val_dir / "ks_metrics.json")
        if m:
            cols = st.columns(3)
            cols[0].metric("final D", f"{m['final_D']:.4f}")
            cols[1].metric("final p-value", f"{m['final_pvalue']:.3f}")
            cols[2].metric("n range", f"{m['n_min']} - {m['n_max']}")
            show_image(val_dir / "ks_curve.png")
        else:
            st.write(t("common.not_available"))
        test_path2 = None if is_demo else st.text_input("FEM results file (.xlsx/.csv)",
                                                        key="ks_test")
        if st.button(t("val.run_ks")):
            args = ["validate", str(project.root), "--no-loocv", "--ks"]
            args += ["--use-pool"] if is_demo else ["--test-xlsx", test_path2 or ""]
            launch_cli(project, args, "validate")
            st.info(t("val.launched"))

    log = tail_file(project.root / "log" / "validate.out")
    if log:
        with st.expander(t("val.log")):
            st.code(log)
