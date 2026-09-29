"""Person 3 Task 3 tests - update and delete API, fully offline.

Run: pytest -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from edge.store import PlaceStore
from tests.conftest import make_place, make_place_payload


@pytest.fixture
def client(tmp_path):
    app = create_app(storage_root=tmp_path)
    with TestClient(app) as c:
        yield c


def test_put_updates_place(client):
    p = make_place_payload(suffix=5, seed=1, confidence=0.5)
    assert client.post("/memory/add", json=p).status_code == 200
    p["confidence"] = 0.99
    r = client.put("/memory/robot-a-5", json=p)
    assert r.status_code == 200, r.text
    assert r.json() == {"id": "robot-a-5"}
    got = client.get("/memory/robot-a-5", params={"agent_id": "robot-a"})
    assert got.status_code == 200
    assert got.json()["confidence"] == pytest.approx(0.99)


def test_put_id_mismatch_rejected(client):
    p = make_place_payload(suffix=5, seed=1)
    r = client.put("/memory/robot-a-6", json=p)
    assert r.status_code == 422


def test_get_missing_returns_404(client):
    r = client.get("/memory/robot-a-999", params={"agent_id": "robot-a"})
    assert r.status_code == 404


def test_get_other_agent_returns_404(client):
    assert (
        client.post("/memory/add", json=make_place_payload(agent="robot-a")).status_code
        == 200
    )
    r = client.get("/memory/robot-a-1", params={"agent_id": "robot-b"})
    assert r.status_code == 404


def test_delete_existing(client):
    assert client.post("/memory/add", json=make_place_payload()).status_code == 200
    r = client.delete("/memory/robot-a-1", params={"agent_id": "robot-a"})
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    assert (
        client.get("/memory/robot-a-1", params={"agent_id": "robot-a"}).status_code
        == 404
    )


def test_delete_missing_returns_404(client):
    r = client.delete("/memory/robot-a-999", params={"agent_id": "robot-a"})
    assert r.status_code == 404


def test_list_returns_page_and_total(client):
    for i in (1, 2, 3):
        assert (
            client.post("/memory/add", json=make_place_payload(suffix=i, seed=i))
        ).status_code == 200
    r = client.get("/memory/list", params={"agent_id": "robot-a", "limit": 50})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert len(body["places"]) == 3


def test_list_empty_store(client):
    r = client.get("/memory/list", params={"agent_id": "robot-a"})
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["places"] == []


def test_list_bad_limit_rejected(client):
    r = client.get("/memory/list", params={"agent_id": "robot-a", "limit": 0})
    assert r.status_code == 422


def test_store_delete(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        store.add(make_place())
        assert store.delete("robot-a-1") is True
        assert store.delete("robot-a-1") is False
        assert store.count() == 0
    finally:
        store.close()
