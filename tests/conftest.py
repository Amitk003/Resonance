"""Shared offline test factories for edge and backend tests."""

from __future__ import annotations

import numpy as np

from edge.config import DIM
from edge.models import Place


def make_vector(seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.random(DIM).tolist()


def make_place(
    agent: str = "robot-a",
    suffix: int = 1,
    seed: int = 0,
    confidence: float = 0.9,
) -> Place:
    return Place(
        id=f"{agent}-{suffix}",
        agent_id=agent,
        vector=make_vector(seed),
        pose={"x": 1.5, "y": 2.0, "theta": 0.4},
        timestamp=1727000000,
        confidence=confidence,
        payload={"zone": "hall", "sensor": "cam", "note": ""},
    )


def make_place_payload(
    agent: str = "robot-a",
    suffix: int = 1,
    seed: int = 0,
    confidence: float = 0.9,
) -> dict:
    return {
        "id": f"{agent}-{suffix}",
        "agent_id": agent,
        "vector": make_vector(seed),
        "pose": {"x": 1.5, "y": 2.0, "theta": 0.4},
        "timestamp": 1727000000,
        "confidence": confidence,
        "payload": {"zone": "hall", "sensor": "cam", "note": ""},
    }
