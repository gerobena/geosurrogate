import pandas as pd
import plotly.express as px
import streamlit as st

from geosurrogate.ui.common import current_project, init_page, load_events, t
from geosurrogate import doe

init_page("doe.title")
project = current_project()
if project:
    cfg = project.config
    X, labels = doe.design(cfg.doe.strategy, cfg.doe.n_lhs, cfg.doe.n_pem,
                           cfg.bounds(), cfg.doe.seed)
    c1, c2, c3 = st.columns(3)
    c1.metric(t("doe.strategy"), cfg.doe.strategy)
    c2.metric(t("doe.total"), len(X))
    c3.metric("seed", cfg.doe.seed)

    events = load_events(project)
    default_s = 150.0
    if len(events) and "elapsed_s" in events.columns:
        done = events[events["type"].isin(["doe_case_done", "al_case_done"])]
        med = done["elapsed_s"].dropna().median() if len(done) else None
        if med and med > 1:
            default_s = float(med)
    sim_s = st.number_input(t("doe.est_time"), min_value=1.0, value=default_s)
    st.metric(t("doe.est_total"), f"{len(X) * sim_s / 3600:.1f} h "
              f"({len(X)} x {sim_s:.0f} s)")

    if st.button(t("doe.preview"), type="primary", key="doe_preview"):
        df = pd.DataFrame(X, columns=cfg.var_ids)
        df["source"] = labels
        if cfg.dims == 2:
            fig = px.scatter(df, x=cfg.var_ids[0], y=cfg.var_ids[1],
                             color="source", height=480)
        else:
            fig = px.scatter_matrix(df, dimensions=cfg.var_ids[:6],
                                    color="source", height=720)
            fig.update_traces(diagonal_visible=False, showupperhalf=False,
                              marker=dict(size=4))
        st.plotly_chart(fig, width="stretch")
        st.dataframe(df.head(30), hide_index=True, width="stretch")
