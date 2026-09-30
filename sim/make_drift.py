"""Two robot drift sim: shared places plus known drift, saved to JSON.

Robot A walks the true path. Robot B sees the same shared places
through a rigid drift (dx, dy, dtheta) plus small noise, plus its
own unique places. Vectors for shared places come from one key
so matching can find them. Saved JSON replays the demo offline.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from edge.config import DIM
from edge.embed import HashEmbedder

TRUE_DX: float = 2.5
TRUE_DY: float = -1.0
TRUE_DTHETA: float = 0.15
NOISE_M: float = 0.05


def apply_drift(x: float, y: float, dx: float, dy: float, dtheta: float) -> tuple[float, float]:
    """Move a world point into the drifted B frame."""
    c, s = math.cos(dtheta), math.sin(dtheta)
    return (c * x - s * y + dx, s * x + c * y + dy)


def make_drift_dataset(
    n_shared: int = 12,
    n_unique: int = 4,
    seed: int = 0,
    drift: tuple[float, float, float] = (TRUE_DX, TRUE_DY, TRUE_DTHETA),
) -> dict:
    """Build replay dict with place lists for robot-a and robot-b."""
    if n_shared < 2:
        raise ValueError("n_shared must be at least 2")
    if n_unique < 0:
        raise ValueError("n_unique must be >= 0")
    dx, dy, dtheta = drift
    rng = np.random.default_rng(seed)
    embed = HashEmbedder(dim=DIM)
    base_time = 1727000000

    robot_a: list[dict] = []
    robot_b: list[dict] = []

    for i in range(n_shared):
        wx = float(i * 1.0)
        wy = float(math.sin(i * 0.5))
        key = f"shared-place-{i}"
        vector = embed.encode_text(key)
        note = "hazard spill" if i == 0 else ""
        robot_a.append(
            {
                "id": f"robot-a-{i + 1}",
                "agent_id": "robot-a",
                "vector": vector,
                "pose": {"x": wx, "y": wy, "theta": 0.0},
                "timestamp": base_time + i,
                "confidence": 0.9,
                "payload": {"zone": "hall", "sensor": "cam", "note": note},
            }
        )
        bx, by = apply_drift(wx, wy, dx, dy, dtheta)
        bx += float(rng.normal(0.0, NOISE_M))
        by += float(rng.normal(0.0, NOISE_M))
        robot_b.append(
            {
                "id": f"robot-b-{i + 1}",
                "agent_id": "robot-b",
                "vector": vector,
                "pose": {"x": bx, "y": by, "theta": dtheta},
                "timestamp": base_time + i,
                "confidence": 0.9,
                "payload": {"zone": "hall", "sensor": "cam", "note": note},
                "shared_index": i,
            }
        )

    for u in range(n_unique):
        for agent in ("robot-a", "robot-b"):
            idx = n_shared + u + 1
            vec = embed.encode_text(f"{agent}-unique-{u}-{seed}")
            robot = robot_a if agent == "robot-a" else robot_b
            robot.append(
                {
                    "id": f"{agent}-{idx}",
                    "agent_id": agent,
                    "vector": vec,
                    "pose": {"x": 50.0 + u, "y": 50.0 + u, "theta": 0.0},
                    "timestamp": base_time + 100 + u,
                    "confidence": 0.5,
                    "payload": {"zone": "far", "sensor": "lidar", "note": ""},
                }
            )

    return {
        "true_transform": {"dx": dx, "dy": dy, "dtheta": dtheta},
        "shared": n_shared,
        "robot_a": robot_a,
        "robot_b": robot_b,
    }


def save_dataset(data: dict, path: Path | str) -> Path:
    """Write dataset JSON. Returns the path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data), encoding="utf-8")
    return out


def load_dataset(path: Path | str) -> dict:
    """Read dataset JSON back."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Make two robot drift JSON")
    parser.add_argument("--shared", type=int, default=12)
    parser.add_argument("--unique", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=str, default="sim/drift.json")
    args = parser.parse_args()
    data = make_drift_dataset(n_shared=args.shared, n_unique=args.unique, seed=args.seed)
    save_dataset(data, args.out)
    print(f"wrote {args.out} shared={args.shared} unique={args.unique}")


if __name__ == "__main__":
    main()
