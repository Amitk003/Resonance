"""Task 6 tests — small swap only, fully offline."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from edge.config import DIM
from edge.store import PlaceStore
from tests.conftest import make_place


def test_pick_swap_empty(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        assert store.pick_swap() == []
    finally:
        store.close()


def test_pick_swap_limit_and_order(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        for i in range(1, 26):
            p = make_place(suffix=i, seed=i, confidence=0.1 + i * 0.03)
            store.add(p)
        # Hazard note bumps to front even with lower confidence.
        hz = make_place(suffix=100, seed=99, confidence=0.2)
        hz.payload.note = "hazard: blocked path"
        store.add(hz)
        got = store.pick_swap(limit=20)
        assert len(got) == 20
        assert got[0].id == "robot-a-100"
        assert all(len(c.vector) == DIM for c in got)
        assert all(c.agent_id == "robot-a" for c in got)
    finally:
        store.close()


def test_pick_swap_bad_limit(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        with pytest.raises(ValueError):
            store.pick_swap(limit=0)
        with pytest.raises(ValueError):
            store.pick_swap(limit=101)
    finally:
        store.close()


def test_pick_swap_isolation(tmp_path):
    a = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    b = PlaceStore(agent_id="robot-b", storage_root=tmp_path)
    try:
        a.add(make_place(agent="robot-a", suffix=1, seed=1))
        assert b.pick_swap() == []
        assert [c.agent_id for c in a.pick_swap()] == ["robot-a"]
    finally:
        a.close()
        b.close()


def test_meet_swap_api(tmp_path):
    app = create_app(storage_root=tmp_path)
    client = TestClient(app)
    for i in (1, 2, 3):
        client.post("/memory/add", json={
            "id": f"robot-a-{i}", "agent_id": "robot-a",
            "vector": make_place(suffix=i, seed=i).vector,
            "pose": {"x": 1.0, "y": 2.0, "theta": 0.1},
            "timestamp": 1727000000 + i, "confidence": 0.5 + i * 0.1,
            "payload": {"zone": "hall", "sensor": "cam", "note": ""},
        }).raise_for_status()
    r = client.post("/meet/swap", json={"agent_id": "robot-a", "limit": 2})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["agent_id"] == "robot-a"
    # Newest + highest confidence first.
    assert body[0]["id"] == "robot-a-3"


def test_meet_swap_api_422(tmp_path):
    app = create_app(storage_root=tmp_path)
    client = TestClient(app)
    assert client.post("/meet/swap", json={"agent_id": "robot-a", "limit": 0}).status_code == 422
    assert client.post("/meet/swap", json={"agent_id": "robot-a", "limit": 101}).status_code == 422
    assert client.post("/meet/swap", json={"agent_id": "", "limit": 5}).status_code == 422
