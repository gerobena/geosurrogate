import numpy as np
import pytest

from geosurrogate.config import Distribution, VariableSpec
from geosurrogate.exploitation import sample_inputs
from geosurrogate.exploitation.sampling import sample_quantiles


def _var(vid, dist):
    return VariableSpec(id=vid, material="M1",
                        property="cohesion" if "coh" in vid else "friction_angle",
                        training_bounds=(0.0, 200.0), distribution=dist)


def test_truncated_normal_respects_bounds_and_moments():
    # the TFM Case-1 cohesion: N(5,1) truncated to [2,6]
    dist = Distribution(family="normal", mean=5.0, std=1.0, truncate=(2.0, 6.0))
    rng = np.random.default_rng(0)
    x = sample_quantiles(dist, rng.uniform(size=50_000))
    assert x.min() >= 2.0 and x.max() <= 6.0
    # truncation [-3sd, +1sd] pulls the mean below 5
    assert 4.5 < x.mean() < 5.0


def test_truncated_halfnormal_like_case2():
    # the TFM Case-2 sand cohesion: N(0,1) truncated to [0,2]
    dist = Distribution(family="normal", mean=0.0, std=1.0, truncate=(0.0, 2.0))
    rng = np.random.default_rng(1)
    x = sample_quantiles(dist, rng.uniform(size=50_000))
    assert x.min() >= 0.0 and x.max() <= 2.0
    assert 0.6 < x.mean() < 0.9  # half-normal-ish mean ~ 0.74

def test_lognormal_positive_and_mean():
    dist = Distribution(family="lognormal", mean=10.0, std=2.0)
    rng = np.random.default_rng(2)
    x = sample_quantiles(dist, rng.uniform(size=50_000))
    assert (x > 0).all()
    assert abs(x.mean() - 10.0) < 0.15


def test_uniform_and_triangular():
    u = Distribution(family="uniform", low=1.0, high=3.0)
    t = Distribution(family="triangular", low=0.0, mode=1.0, high=4.0)
    rng = np.random.default_rng(3)
    xu = sample_quantiles(u, rng.uniform(size=20_000))
    xt = sample_quantiles(t, rng.uniform(size=20_000))
    assert 1.0 <= xu.min() and xu.max() <= 3.0
    assert 0.0 <= xt.min() and xt.max() <= 4.0
    assert abs(xt.mean() - (0 + 1 + 4) / 3) < 0.05


def test_sample_inputs_deterministic_and_shaped():
    variables = [
        _var("coh", Distribution(family="normal", mean=5, std=1, truncate=(2, 6))),
        _var("phi", Distribution(family="uniform", low=25, high=34)),
    ]
    a = sample_inputs(variables, 500, seed=7)
    b = sample_inputs(variables, 500, seed=7)
    assert list(a.columns) == ["coh", "phi"]
    assert a.shape == (500, 2)
    assert np.allclose(a.to_numpy(), b.to_numpy())
