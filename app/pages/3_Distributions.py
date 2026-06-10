import numpy as np
import plotly.graph_objects as go
import streamlit as st

from geosurrogate.ui.common import current_project, init_page, t
from geosurrogate.exploitation.sampling import _frozen

init_page("dist.title")
project = current_project()
if project:
    st.info(t("dist.note"))
    for v in project.config.variables:
        d = v.distribution
        frozen = _frozen(d)
        lo, hi = v.training_bounds
        span = hi - lo
        x = np.linspace(lo - 0.15 * span, hi + 0.15 * span, 400)
        pdf = frozen.pdf(x)
        if d.truncate is not None:
            mask = (x < d.truncate[0]) | (x > d.truncate[1])
            pdf = np.where(mask, np.nan, pdf)

        fig = go.Figure()
        fig.add_vrect(x0=lo, x1=hi, fillcolor="#2ecc71", opacity=0.12, line_width=0)
        fig.add_trace(go.Scatter(x=x, y=pdf, mode="lines", name=d.family,
                                 line=dict(width=3, color="#2980b9")))
        if d.truncate is not None:
            for tx in d.truncate:
                fig.add_vline(x=tx, line_dash="dash", line_color="red")
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=40, b=10),
                          title=f"{v.id} - {v.material} / {v.property} "
                                f"({d.family})", showlegend=False)
        st.plotly_chart(fig, width="stretch")

        cols = st.columns(4)
        if d.family in ("normal", "lognormal"):
            cols[0].metric("mean", f"{d.mean:g}")
            cols[1].metric("std", f"{d.std:g}")
        elif d.family == "uniform":
            cols[0].metric("low", f"{d.low:g}")
            cols[1].metric("high", f"{d.high:g}")
        else:
            cols[0].metric("low / mode / high", f"{d.low:g} / {d.mode:g} / {d.high:g}")
        cols[2].metric("truncate", f"{d.truncate[0]:g} - {d.truncate[1]:g}"
                       if d.truncate else "-")
        cols[3].metric("training box", f"{lo:g} - {hi:g}")
