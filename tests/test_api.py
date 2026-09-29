"""Person 2 Task 2 tests - write and search API, fully offline.

Run: pytest -v
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from edge.config import DIM


def make_vector(seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.random(DIM).tolist()


def make_place_payload(
    agent: str = "robot-a", suffix: int = 1, seed: int = 0, confidence: float = 0.9
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


@pytest.fixture
def client(tmp_path):
    app = create_app(storage_root=tmp_path)
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_add_returns_id(client):
    r = client.post("/memory/add", json=make_place_payload())
    assert r.status_code == 200, r.text
    assert r.json() == {"id": "robot-a-1"}


def test_add_then_search_top_match(client):
    p1 = make_place_payload(suffix=1, seed=1)
    p2 = make_place_payload(suffix=2, seed=2)
    assert client.post("/memory/add", json=p1).status_code == 200
    assert client.post("/memory/add", json=p2).status_code == 200
    # Query with p1's own vector - p1 must be the top hit.
    r = client.post(
        "/memory/search",
        json={"agent_id": "robot-a", "vector": p1["vector"], "top_k": 5},
    )
    assert r.status_code == 200, r.text
    hits = r.json()
    assert len(hits) == 2
    assert hits[0]["id"] == "robot-a-1"
    assert hits[0]["score"] == pytest.approx(1.0, abs=1e-4)
    assert hits[0]["place"]["id"] == "robot-a-1"


def test_search_empty_store(client):
    r = client.post(
        "/memory/search",
        json={"agent_id": "robot-a", "vector": make_vector(0), "top_k": 5},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_search_respects_top_k(client):
    for i in (1, 2, 3):
        assert (
            client.post(
                "/memory/add", json=make_place_payload(suffix=i, seed=i)
            ).status_code
            == 200
        )
    r = client.post(
        "/memory/search",
        json={"agent_id": "robot-a", "vector": make_vector(1), "top_k": 1},
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_search_respects_min_confidence(client):
    low = make_place_payload(suffix=1, seed=1, confidence=0.2)
    high = make_place_payload(suffix=2, seed=1, confidence=0.95)
    assert client.post("/memory/add", json=low).status_code == 200
    assert client.post("/memory/add", json=high).status_code == 200
    r = client.post(
        "/memory/search",
        json={
            "agent_id": "robot-a",
            "vector": make_vector(1),
            "top_k": 5,
            "min_confidence": 0.9,
        },
    )
    assert r.status_code == 200, r.text
    hits = r.json()
    assert len(hits) == 1
    assert hits[0]["id"] == "robot-a-2"


def test_search_isolated_per_agent(client):
    assert (
        client.post("/memory/add", json=make_place_payload(agent="robot-a")).status_code
        == 200
    )
    r = client.post(
        "/memory/search",
        json={"agent_id": "robot-b", "vector": make_vector(0), "top_k": 5},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_add_invalid_vector_rejected(client):
    bad = make_place_payload()
    bad["vector"] = [0.0] * 511
    r = client.post("/memory/add", json=bad)
    assert r.status_code == 422


def test_search_invalid_vector_rejected(client):
    r = client.post(
        "/memory/search",
        json={"agent_id": "robot-a", "vector": [0.0] * 10, "top_k": 5},
    )
    assert r.status_code == 422


def test_upsert_same_id_overwrites(client):
    p = make_place_payload(suffix=42, seed=1, confidence=0.5)
    assert client.post("/memory/add", json=p).status_code == 200
    p2 = make_place_payload(suffix=42, seed=2, confidence=0.95)
    assert client.post("/memory/add", json=p2).status_code == 200
    r = client.post(
        "/memory/search",
        json={"agent_id": "robot-a", "vector": p2["vector"], "top_k": 5},
    )
    assert r.status_code == 200
    hits = r.json()
    assert hits[0]["id"] == "robot-a-42"
    assert hits[0]["place"]["confidence"] == pytest.approx(0.95)
