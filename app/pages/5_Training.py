import datetime as dt

import plotly.graph_objects as go
import streamlit as st

from geosurrogate.ui.common import current_project, init_page, load_events, t
from geosurrogate.activelearning import runner

init_page("train.title")
project = current_project()
if project:
    cfg = project.config

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button(t("train.start"), type="primary"):
            pid = runner.launch_detached(project.root)
            st.success(t("train.launched", pid=pid))
    with col_b:
        if st.button(t("train.pause")):
            runner.request_pause(project.root)
            st.warning(t("train.pause_req"))

    @st.fragment(run_every=2)
    def live_view():
        state = project.read_state()
        running = state.get("status") == "running"
        cols = st.columns(5)
        cols[0].metric(t("train.phase"), state.get("phase", "-"))
        cols[1].metric(t("train.status"), state.get("status", "-"))
        cols[2].metric(t("train.sims"),
                       f"{state.get('n_samples', 0)} / {state.get('budget_total', '-')}")
        cols[3].metric(t("train.iteration"), state.get("iteration", 0))
        err = state.get("error_max")
        cols[4].metric(t("train.error"), f"{err:.5f}" if err is not None else "-")

        budget = state.get("budget_total") or cfg.active_learning.budget_total_sims
        n_done = int(state.get("n_samples") or 0)
        if n_done or running:
            st.progress(min(n_done / budget, 1.0),
                        text=t("train.progress", done=n_done, total=budget))
        if state.get("status") == "finished":
            reason = state.get("stop_reason", "")
            if reason == "converged":
                st.success(t("train.done_converged"))
            else:
                st.info(t("train.done_other", reason=reason))
            flag = f"celebrated_{project.root}"
            if reason == "converged" and not st.session_state.get(flag):
                st.balloons()
                st.session_state[flag] = True

        if running and state.get("updated_at"):
            age = (dt.datetime.now()
                   - dt.datetime.fromisoformat(state["updated_at"])).total_seconds()
            if age > 600:
                st.warning(t("train.stale"))

        events = load_events(project)
        # early in a run only DoE events exist and the error_max column is absent
        if len(events) and "error_max" in events.columns:
            iters = events[events["type"] == "al_iteration"].dropna(subset=["error_max"])
            if len(iters):
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=iters["iteration"], y=iters["error_max"],
                                         mode="lines+markers", name="error_max",
                                         line=dict(color="#2980b9", width=2.5)))
                tol = cfg.active_learning.tolerance
                fig.add_hline(y=tol, line_dash="dash", line_color="red",
                              annotation_text=f"{t('train.tolerance')} = {tol:g}")
                fig.update_yaxes(type="log")
                fig.update_layout(title=t("train.convergence"), height=380,
                                  xaxis_title=t("train.iteration"),
                                  yaxis_title="max |delta SRF|",
                                  margin=dict(l=10, r=10, t=50, b=10))
                st.plotly_chart(fig, width="stretch")

        ds = project.load_dataset()
        if len(ds):
            st.caption(t("train.dataset_tail"))
            st.dataframe(ds.tail(8), hide_index=True, width="stretch")

    live_view()
