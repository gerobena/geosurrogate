import pytest

from geosurrogate.solvers.base import MaterialInfo
from geosurrogate.ui import wizard


def _mats():
    return [
        MaterialInfo(name="embankment", index=0,
                     current_values={"peak_cohesion": 100.0,
                                     "peak_friction_angle": 25.0}),
        MaterialInfo(name="sand", index=1,
                     current_values={"peak_cohesion": 0.0,
                                     "peak_friction_angle": 35.0}),
    ]


def test_editor_rows_defaults():
    df = wizard.editor_rows(_mats())
    assert len(df) == 4  # 2 materials x 2 properties
    coh_sand = df[(df["material"] == "sand") & (df["property"] == "cohesion")].iloc[0]
    assert coh_sand["mean"] == 0.0
    assert coh_sand["low"] == 0.0          # cohesion floored at zero
    assert coh_sand["std"] == 0.5          # minimum std for zero-mean
    phi_emb = df[(df["material"] == "embankment")
                 & (df["property"] == "friction_angle")].iloc[0]
    assert phi_emb["mean"] == 25.0
    assert phi_emb["low"] == pytest.approx(25.0 - 3 * 2.5)
    assert not df["include"].any()


def test_rows_to_variables_builds_valid_specs():
    df = wizard.editor_rows(_mats())
    df.loc[(df["material"] == "embankment"), "include"] = True
    df.loc[(df["material"] == "sand") & (df["property"] == "cohesion"),
           "include"] = True
    variables = wizard.rows_to_variables(df)
    assert [v.id for v in variables] == ["coh_embankment", "phi_embankment",
                                         "coh_sand"]
    v = variables[0]
    assert v.training_bounds == v.distribution.truncate
    assert v.distribution.family == "normal"


def test_rows_to_variables_uniform_and_errors():
    df = wizard.editor_rows(_mats())
    df.loc[0, "include"] = True
    df.loc[0, "family"] = "uniform"
    variables = wizard.rows_to_variables(df)
    assert variables[0].distribution.family == "uniform"
    assert variables[0].distribution.low == variables[0].training_bounds[0]

    df.loc[0, "low"], df.loc[0, "high"] = 5.0, 1.0
    with pytest.raises(ValueError, match="low must be"):
        wizard.rows_to_variables(df)

    with pytest.raises(ValueError, match="at least one"):
        wizard.rows_to_variables(wizard.editor_rows(_mats()))


def test_recommend_doe_by_dimension():
    assert wizard.recommend_doe(2) == {"strategy": "factorial_3", "n_lhs": 0,
                                       "n_pem": 0, "design_size": 9,
                                       "budget": 39}
    assert wizard.recommend_doe(3)["design_size"] == 27
    rec8 = wizard.recommend_doe(8)
    assert rec8["strategy"] == "hybrid_lhs_pem"
    assert rec8["n_lhs"] == 80 and rec8["n_pem"] == 40


def test_slug():
    assert wizard.slug("Foundation Clay (upper)") == "foundation_clay_upper"
    assert wizard.slug("***") == "mat"
