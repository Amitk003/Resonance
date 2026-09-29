"""Task 10 tests - rigid transform only, fully offline, numpy only."""

from __future__ import annotations

import math

import numpy as np

from edge.align import estimate_transform


def make_drifted(n: int = 12, seed: int = 0):
    """Sim two drifted paths: A base grid, B = known transform + noise."""
    rng = np.random.default_rng(seed)
    a = np.column_stack([rng.uniform(0, 10, n), rng.uniform(0, 10, n)])
    dx, dy, dt = 0.5, -0.2, 0.05
    c, s = math.cos(dt), math.sin(dt)
    # B is A shifted by inverse transform + small noise (drifted robot).
    r_inv = np.array([[c, s], [-s, c]])
    b = (a - np.array([dx, dy])) @ r_inv.T + rng.normal(0, 0.05, (n, 2))
    pairs = [(float(a[i, 0]), float(a[i, 1]), float(b[i, 0]), float(b[i, 1])) for i in range(n)]
    return pairs, dx, dy, dt


def ang_diff(x: float, y: float) -> float:
    d = abs(x - y) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def test_estimate_known_drift():
    pairs, dx, dy, dt = make_drifted()
    est = estimate_transform(pairs)
    assert est is not None
    assert abs(est.dx - dx) < 0.3
    assert abs(est.dy - dy) < 0.3
    assert ang_diff(est.dtheta, dt) < math.radians(5)
    assert est.inliers >= 10
    assert est.shape_fit >= 0.8


def test_rejects_random_pairs():
    rng = np.random.default_rng(7)
    pairs = [
        (float(rng.uniform(0, 10)), float(rng.uniform(0, 10)),
         float(rng.uniform(0, 10)), float(rng.uniform(0, 10)))
        for _ in range(12)
    ]
    est = estimate_transform(pairs, seed=1)
    assert est is None or est.inliers < 4


def test_needs_two_pairs():
    assert estimate_transform([]) is None
    assert estimate_transform([(0.0, 0.0, 0.5, 0.1)]) is None


def test_bad_input_rejected():
    import pytest

    with pytest.raises(ValueError):
        estimate_transform([(0.0, 0.0, float("nan"), 0.0), (1.0, 1.0, 2.0, 2.0)])


def test_deterministic():
    pairs, _, _, _ = make_drifted(seed=3)
    e1 = estimate_transform(pairs, seed=0)
    e2 = estimate_transform(pairs, seed=0)
    assert e1 is not None and e2 is not None
    assert (e1.dx, e1.dy, e1.dtheta) == (e2.dx, e2.dy, e2.dtheta)
