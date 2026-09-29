"""Task 1 tests — storage-only, fully offline.

No internet, no server, no Docker, no model downloads.
Run: pytest -v
"""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError
from qdrant_client.models import Distance

from edge.config import DIM
from edge.models import Place
from edge.store import PlaceStore


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


def test_collection_config(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        info = store._client.get_collection(store.collection)
        assert info.config.params.vectors.size == DIM
        assert info.config.params.vectors.distance == Distance.COSINE
    finally:
        store.close()


def test_add_get_count(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        p = make_place()
        pid = store.add(p)
        assert pid == "robot-a-1"
        saved = store.get(pid)
        assert saved is not None
        assert saved.id == p.id
        assert saved.agent_id == "robot-a"
        # Qdrant COSINE distance L2-normalizes stored vectors, so compare
        # direction (cosine similarity ~1), not raw magnitude.
        a = np.array(saved.vector)
        b = np.array(p.vector)
        cos = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
        assert cos == pytest.approx(1.0, abs=1e-5)
        assert saved.pose.x == pytest.approx(1.5)
        assert saved.confidence == pytest.approx(0.9)
        assert saved.payload.zone == "hall"
        assert store.count() == 1
    finally:
        store.close()


def test_count_three(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        for i in (1, 2, 3):
            store.add(make_place(suffix=i, seed=i))
        assert store.count() == 3
    finally:
        store.close()


def test_clear(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        store.add(make_place(suffix=1, seed=1))
        store.clear()
        assert store.count() == 0
    finally:
        store.close()


def test_persistence(tmp_path):
    root = tmp_path / "edge"
    s1 = PlaceStore(agent_id="robot-a", storage_root=root)
    s1.add(make_place(suffix=7, seed=7))
    s1.close()
    # Reopen same path — data must survive restart.
    s2 = PlaceStore(agent_id="robot-a", storage_root=root)
    try:
        saved = s2.get("robot-a-7")
        assert saved is not None
        assert saved.id == "robot-a-7"
    finally:
        s2.close()


def test_missing_id_returns_none(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        assert store.get("robot-a-999") is None
    finally:
        store.close()


def test_upsert_same_id(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        store.add(make_place(suffix=42, seed=1, confidence=0.5))
        store.add(make_place(suffix=42, seed=2, confidence=0.95))
        assert store.count() == 1
        saved = store.get("robot-a-42")
        assert saved is not None
        assert saved.confidence == pytest.approx(0.95)
    finally:
        store.close()


def test_invalid_vector_rejected():
    with pytest.raises(ValidationError):
        Place(
            id="robot-a-1",
            agent_id="robot-a",
            vector=[0.0] * 511,
            pose={"x": 0.0, "y": 0.0, "theta": 0.0},
            timestamp=1,
            confidence=0.5,
            payload={"zone": "", "sensor": "", "note": ""},
        )
    with pytest.raises(ValidationError):
        Place(
            id="robot-a-1",
            agent_id="robot-a",
            vector=[0.0] * 513,
            pose={"x": 0.0, "y": 0.0, "theta": 0.0},
            timestamp=1,
            confidence=0.5,
            payload={"zone": "", "sensor": "", "note": ""},
        )


def test_invalid_confidence_rejected():
    with pytest.raises(ValidationError):
        make_place(confidence=-0.1)
    with pytest.raises(ValidationError):
        make_place(confidence=1.1)


def test_agent_isolation(tmp_path):
    a = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    b = PlaceStore(agent_id="robot-b", storage_root=tmp_path)
    try:
        a.add(make_place(agent="robot-a", suffix=1, seed=1))
        # B's local DB must not contain A's place.
        assert b.get("robot-a-1") is None
        assert b.count() == 0
        assert a.count() == 1
        # Cross-agent add must be rejected.
        with pytest.raises(ValueError):
            b.add(make_place(agent="robot-a", suffix=2, seed=2))
    finally:
        a.close()
        b.close()


def test_zero_vector_offline(tmp_path):
    """Deterministic zero vector works with no model download."""
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        p = Place(
            id="robot-a-1",
            agent_id="robot-a",
            vector=np.zeros(DIM).tolist(),
            pose={"x": 0.0, "y": 0.0, "theta": 0.0},
            timestamp=1,
            confidence=0.5,
            payload={"zone": "", "sensor": "", "note": ""},
        )
        store.add(p)
        assert store.get("robot-a-1") is not None
    finally:
        store.close()
