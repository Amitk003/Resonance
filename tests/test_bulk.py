"""Refine 2 commit 1: bulk import so seeding needs one request."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import create_app
from tests.conftest import make_place_payload


def _client(tmp_path):
    app = create_app(storage_root=tmp_path)
    with TestClient(app) as c:
        yield c


import pytest


@pytest.fixture
def client(tmp_path):
    yield from _client(tmp_path)


def test_bulk_adds_many(client):
    places = [make_place_payload(suffix=i, seed=i) for i in range(1, 19)]
    r = client.post("/memory/bulk", json=places)
    assert r.status_code == 200, r.text
    assert len(r.json()["ids"]) == 18
    check = client.get("/memory/list", params={"agent_id": "robot-a", "limit": 50})
    assert check.json()["total"] == 18


def test_bulk_rejects_empty(client):
    r = client.post("/memory/bulk", json=[])
    assert r.status_code == 422


def test_bulk_rejects_over_limit(client):
    places = [make_place_payload(suffix=i, seed=i) for i in range(1, 202)]
    for p in places:
        p["id"] = f"robot-a-{p['id']}-{p['vector'][0]}"
    # ids above reuse suffix pattern but must stay unique; rebuild simply
    seen = set()
    for i, p in enumerate(places):
        p["id"] = f"robot-a-{i}"
    r = client.post("/memory/bulk", json=places)
    assert r.status_code == 422


def test_bulk_rejects_bad_vector(client):
    places = [make_place_payload(suffix=1, seed=1)]
    places[0]["vector"] = [0.0] * 10
    r = client.post("/memory/bulk", json=places)
    assert r.status_code == 422


def test_bulk_groups_mixed_agents(client):
    a = make_place_payload(agent="robot-a", suffix=1, seed=1)
    b = make_place_payload(agent="robot-b", suffix=1, seed=2)
    r = client.post("/memory/bulk", json=[a, b])
    assert r.status_code == 200, r.text
    assert sorted(r.json()["ids"]) == ["robot-a-1", "robot-b-1"]
