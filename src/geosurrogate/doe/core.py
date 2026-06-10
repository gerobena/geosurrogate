"""Design of Experiments: LHS, PEM corner designs and the hybrid LHS+PEM strategy.

All functions are N-dimensional and return points in real (unscaled) space.
`bounds` is a sequence of (low, high) per variable.
"""

from __future__ import annotations

import itertools

import numpy as np
from scipy.spatial.distance import cdist
from scipy.stats import qmc
from sklearn.cluster import KMeans

Bounds = list[tuple[float, float]]


def _bounds_arrays(bounds: Bounds) -> tuple[np.ndarray, np.ndarray]:
    arr = np.asarray(bounds, dtype=float)
    return arr[:, 0], arr[:, 1]


def to_unit(X: np.ndarray, bounds: Bounds) -> np.ndarray:
    low, high = _bounds_arrays(bounds)
    return (np.asarray(X, dtype=float) - low) / (high - low)


def from_unit(U: np.ndarray, bounds: Bounds) -> np.ndarray:
    low, high = _bounds_arrays(bounds)
    return low + np.asarray(U, dtype=float) * (high - low)


def lhs(n: int, bounds: Bounds, seed: int, optimize: bool = False) -> np.ndarray:
    """Latin Hypercube design. `optimize=True` mirrors the TFM's space-filling
    variant (scipy 'random-cd' discrepancy optimization)."""
    d = len(bounds)
    if n == 0:
        return np.empty((0, d))
    sampler = qmc.LatinHypercube(d=d, seed=seed, optimization="random-cd" if optimize else None)
    return from_unit(sampler.random(n=n), bounds)


def pem_corners(bounds: Bounds) -> np.ndarray:
    """All 2^D vertices of the training box (Point Estimate Method support points)."""
    return np.array(list(itertools.product(*[(lo, hi) for lo, hi in bounds])), dtype=float)


def pem_kmeans(n: int, bounds: Bounds, seed: int) -> np.ndarray:
    """Representative subset of the 2^D corners via K-Means on the unit cube
    (ported from the TFM hybrid DoE generator). Returns all corners when 2^D <= n."""
    corners = pem_corners(bounds)
    if len(corners) <= n:
        return corners
    unit = to_unit(corners, bounds)
    km = KMeans(n_clusters=n, random_state=seed, n_init=10).fit(unit)
    chosen: list[int] = []
    for center in km.cluster_centers_:
        order = np.argsort(cdist([center], unit)[0])
        for idx in order:
            if idx not in chosen:
                chosen.append(int(idx))
                break
    return corners[np.array(chosen)]


def design(strategy: str, n_lhs: int, n_pem: int, bounds: Bounds, seed: int) -> tuple[np.ndarray, list[str]]:
    """Initial design in real space, with a per-point source label. The row
    order is deterministic for a given seed, which makes resuming a partially
    simulated design trivial (skip the first len(dataset) rows)."""
    if strategy == "lhs":
        X, labels = lhs(n_lhs, bounds, seed), ["lhs"] * n_lhs
    elif strategy == "lhs_maximin":
        X, labels = lhs(n_lhs, bounds, seed, optimize=True), ["lhs_maximin"] * n_lhs
    elif strategy == "pem":
        X = pem_kmeans(n_pem, bounds, seed)
        labels = ["pem"] * len(X)
    elif strategy == "hybrid_lhs_pem":
        X_l = lhs(n_lhs, bounds, seed, optimize=True)
        X_p = pem_kmeans(n_pem, bounds, seed)
        X = np.vstack([X_l, X_p])
        labels = ["lhs_maximin"] * len(X_l) + ["pem"] * len(X_p)
    else:
        raise ValueError(f"unknown DoE strategy: {strategy}")
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(X))
    return X[order], [labels[i] for i in order]


def select_from_pool(target: np.ndarray, pool: np.ndarray, bounds: Bounds) -> list[int]:
    """Greedy nearest-neighbour matching of a target design onto a finite pool
    (demo mode). Returns unique positional indices into `pool`."""
    if len(target) > len(pool):
        raise ValueError(f"pool too small: need {len(target)}, have {len(pool)}")
    t_unit = to_unit(target, bounds)
    p_unit = to_unit(pool, bounds)
    dist = cdist(t_unit, p_unit)
    chosen: list[int] = []
    for i in range(len(target)):
        for idx in np.argsort(dist[i]):
            if int(idx) not in chosen:
                chosen.append(int(idx))
                break
    return chosen
