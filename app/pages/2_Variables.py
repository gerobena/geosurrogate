import pandas as pd
import streamlit as st

from geosurrogate.ui.common import current_project, init_page, t

init_page("vars.title")
project = current_project()
if project:
    cfg = project.config
    st.metric(t("vars.dims"), f"{cfg.dims}D")
    st.info(t("vars.note"))
    rows = [{
        "id": v.id,
        "material": v.material,
        "property": v.property,
        "low": v.training_bounds[0],
        "high": v.training_bounds[1],
        "distribution": v.distribution.family,
    } for v in cfg.variables]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(t("vars.table_caption"))
