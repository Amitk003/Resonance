"""Shape check and rigid transform (Task 10, math only).

Takes Task 9 candidate pairs as 2D points, RANSAC-fits the rigid
transform moving map B into map A. Pure numpy, fully offline.
No threshold gate (Task 13), no endpoint (Task 14), no sync here.
"""

from __future__ import annotations

import math

import numpy as np


def _fit_two(a1: np.ndarray, a2: np.ndarray, b1: np.ndarray, b2: np.ndarray) -> tuple[float, float, float]:
    """Fit rigid B->A from 2 point pairs. Returns (dx, dy, dtheta)."""
    da = a2 - a1
    db = b2 - b1
    dtheta = float(math.atan2(da[1], da[0]) - math.atan2(db[1], db[0]))
    c, s = math.cos(dtheta), math.sin(dtheta)
    r00, r01, r10, r11 = c, -s, s, c
    t = a1 - np.array([r00 * b1[0] + r01 * b1[1], r10 * b1[0] + r11 * b1[1]])
    return float(t[0]), float(t[1]), float(dtheta)


def _fit_kabsch(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """Least-squares rigid B->A on N>=2 pairs. Returns (dx, dy, dtheta)."""
    ca = a.mean(axis=0)
    cb = b.mean(axis=0)
    h = (b - cb).T @ (a - ca)
    u, _, vt = np.linalg.svd(h)
    r = vt.T @ u.T
    if float(np.linalg.det(r)) < 0.0:
        vt[-1, :] *= -1.0
        r = vt.T @ u.T
    dtheta = float(math.atan2(r[1, 0], r[0, 0]))
    t = ca - r @ cb
    return float(t[0]), float(t[1]), dtheta


def _apply(b: np.ndarray, dx: float, dy: float, dtheta: float) -> np.ndarray:
    c, s = math.cos(dtheta), math.sin(dtheta)
    r = np.array([[c, -s], [s, c]])
    return b @ r.T + np.array([dx, dy])


class AlignEstimate:
    """Result of estimate_transform. Lightweight, no pydantic needed."""

    __slots__ = ("dx", "dy", "dtheta", "inliers", "total")

    def __init__(self, dx: float, dy: float, dtheta: float, inliers: int, total: int) -> None:
        self.dx = dx
        self.dy = dy
        self.dtheta = dtheta
        self.inliers = inliers
        self.total = total

    @property
    def shape_fit(self) -> float:
        return self.inliers / self.total if self.total else 0.0


def estimate_transform(
    pairs: list[tuple[float, float, float, float]],
    inlier_thresh: float = 0.5,
    iters: int = 100,
    seed: int = 0,
) -> AlignEstimate | None:
    """RANSAC rigid fit of B points into A points.

    Args:
        pairs: list of (ax, ay, bx, by), A=own map, B=other map.
        inlier_thresh: meters; a pair is an inlier when mapped error below it.
        iters: RANSAC rounds. seed: determinism for tests.

    Returns:
        AlignEstimate or None when fewer than 2 pairs or no consensus.
        No threshold gate here; Task 13 decides fuse vs log.
    """
    n = len(pairs)
    if n < 2:
        return None
    arr = np.array(pairs, dtype=float)
    if arr.shape != (n, 4) or not np.all(np.isfinite(arr)):
        raise ValueError("pairs must be a list of (ax, ay, bx, by) numbers")
    a = arr[:, :2]
    b = arr[:, 2:]
    rng = np.random.default_rng(seed)
    best: AlignEstimate | None = None
    best_idx: np.ndarray = np.zeros(0, dtype=int)
    for _ in range(max(1, iters)):
        i, j = rng.choice(n, size=2, replace=False)
        try:
            dx, dy, dt = _fit_two(a[i], a[j], b[i], b[j])
        except Exception:
            continue
        err = np.linalg.norm(_apply(b, dx, dy, dt) - a, axis=1)
        idx = np.nonzero(err < inlier_thresh)[0]
        if best is None or len(idx) > len(best_idx):
            best_idx = idx
            if len(idx) >= 2:
                rdx, rdy, rdt = _fit_kabsch(a[idx], b[idx])
            else:
                rdx, rdy, rdt = dx, dy, dt
            best = AlignEstimate(rdx, rdy, rdt, len(idx), n)
            if len(idx) == n:
                break
    if best is None or best.inliers < 2:
        return None
    # Final refit on consensus set.
    err = np.linalg.norm(_apply(b, best.dx, best.dy, best.dtheta) - a, axis=1)
    idx = np.nonzero(err < inlier_thresh)[0]
    if len(idx) >= 2:
        dx, dy, dt = _fit_kabsch(a[idx], b[idx])
        return AlignEstimate(dx, dy, dt, len(idx), n)
    return best
