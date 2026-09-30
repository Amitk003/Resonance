"""Person 2 Task 14 tests - sync queue plus live threshold, offline."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from tests.conftest import make_place_payload


@pytest.fixture
def client(tmp_path):
    app = create_app(storage_root=tmp_path)
    with TestClient(app) as c:
        yield c


def test_queue_orders_hazards_first(client):
    plain = make_place_payload(suffix=1, seed=1, confidence=0.99)
    hazard = make_place_payload(suffix=2, seed=2, confidence=0.1)
    hazard["payload"] = {"zone": "hall", "sensor": "cam", "note": "hazard"}
    assert client.post("/memory/add", json=plain).status_code == 200
    assert client.post("/memory/add", json=hazard).status_code == 200
    r = client.get("/sync/queue", params={"agent_id": "robot-a"})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["place"]["id"] for row in rows] == ["robot-a-2", "robot-a-1"]
    assert rows[0]["reasons"] == ["hazard"]


def test_queue_empty_store(client):
    r = client.get("/sync/queue", params={"agent_id": "robot-a"})
    assert r.status_code == 200
    assert r.json() == []


def test_queue_bad_limit_rejected(client):
    r = client.get("/sync/queue", params={"agent_id": "robot-a", "limit": 0})
    assert r.status_code == 422


def test_queue_anchors_from_history(client):
    for i, (x, y) in enumerate([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], start=1):
        for agent in ("robot-a", "robot-b"):
            payload = make_place_payload(agent=agent, suffix=i, seed=i)
            payload["pose"] = {"x": x, "y": y, "theta": 0.0}
            payload["confidence"] = 0.5
            assert client.post("/memory/add", json=payload).status_code == 200
    r = client.post("/meet/align", json={"agent_a": "robot-a", "agent_b": "robot-b"})
    assert r.status_code == 200, r.text
    q = client.get("/sync/queue", params={"agent_id": "robot-a"})
    assert q.status_code == 200
    assert all("anchor" in row["reasons"] for row in q.json())


def test_threshold_default_and_move(client):
    r = client.get("/fuse/threshold")
    assert r.status_code == 200
    assert r.json() == {"threshold": 0.8}
    r = client.put("/fuse/threshold", json={"threshold": 0.6})
    assert r.status_code == 200
    assert r.json() == {"threshold": 0.6}
    assert client.get("/fuse/threshold").json() == {"threshold": 0.6}


def test_threshold_bad_value_rejected(client):
    assert client.put("/fuse/threshold", json={"threshold": 1.5}).status_code == 422
    assert client.put("/fuse/threshold", json={"threshold": -0.1}).status_code == 422
    assert client.get("/fuse/threshold").json() == {"threshold": 0.8}
