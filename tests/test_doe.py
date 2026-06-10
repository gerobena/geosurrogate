import numpy as np
import pytest

from geosurrogate import doe

BOUNDS_3D = [(0.0, 10.0), (100.0, 200.0), (-5.0, 5.0)]


def test_lhs_shape_and_bounds():
    X = doe.lhs(20, BOUNDS_3D, seed=1)
    assert X.shape == (20, 3)
    for j, (lo, hi) in enumerate(BOUNDS_3D):
        assert X[:, j].min() >= lo and X[:, j].max() <= hi


def test_lhs_deterministic_per_seed():
    a = doe.lhs(10, BOUNDS_3D, seed=7)
    b = doe.lhs(10, BOUNDS_3D, seed=7)
    c = doe.lhs(10, BOUNDS_3D, seed=8)
    assert np.allclose(a, b)
    assert not np.allclose(a, c)


def test_pem_corners_count():
    corners = doe.pem_corners(BOUNDS_3D)
    assert corners.shape == (8, 3)
    assert {tuple(c) for c in corners[:, 0:1].tolist()} <= {(0.0,), (10.0,)}


def test_pem_kmeans_returns_all_when_few_corners():
    out = doe.pem_kmeans(10, BOUNDS_3D, seed=0)   # 2^3 = 8 <= 10
    assert out.shape == (8, 3)


def test_pem_kmeans_subset_unique():
    bounds_5d = [(0.0, 1.0)] * 5                   # 32 corners
    out = doe.pem_kmeans(12, bounds_5d, seed=0)
    assert out.shape == (12, 5)
    assert len(np.unique(out, axis=0)) == 12


def test_hybrid_design_counts_and_labels():
    X, labels = doe.design("hybrid_lhs_pem", n_lhs=6, n_pem=4, bounds=BOUNDS_3D, seed=42)
    assert X.shape == (10, 3)
    assert sorted(set(labels)) == ["lhs_maximin", "pem"]
    assert labels.count("pem") == 4


def test_select_from_pool_unique_and_nearest():
    rng = np.random.default_rng(0)
    pool = rng.uniform([b[0] for b in BOUNDS_3D], [b[1] for b in BOUNDS_3D], size=(50, 3))
    target = pool[[3, 17, 33]] + 1e-9
    idx = doe.select_from_pool(target, pool, BOUNDS_3D)
    assert idx == [3, 17, 33]
    assert len(set(idx)) == 3


def test_select_from_pool_too_small():
    pool = np.zeros((2, 3))
    with pytest.raises(ValueError):
        doe.select_from_pool(np.zeros((3, 3)), pool, BOUNDS_3D)
