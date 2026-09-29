"""Centralized configuration for Resonance Task 1.

Single source of truth so all 4 team members use the same values.
Matches docs/tech-stack.md and docs/data-model.md.

Layout:
    config.py
        |
        v
    models.py -> store.py -> Qdrant Local -> ./edge_data/<agent_id>/
"""

from __future__ import annotations

from pathlib import Path

# Vector dimension - must be identical for every agent.
DIM: int = 512

# Qdrant collection holding places for one agent.
COLLECTION_NAME: str = "places"

# Repo root = parent of this file's directory (Resonance/edge/ -> Resonance/).
# Storage layout: <repo_root>/edge_data/<agent_id>/
EDGE_DATA_ROOT: Path = Path(__file__).resolve().parents[1] / "edge_data"


def agent_path(agent_id: str, root: Path | str | None = None) -> Path:
    """Return the isolated Qdrant storage path for one agent.

    Each robot gets its own directory so Robot A and Robot B never
    share a local DB when simulated on the same machine.
    """
    base = Path(root) if root is not None else EDGE_DATA_ROOT
    return base / agent_id
