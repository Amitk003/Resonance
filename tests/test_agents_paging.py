"""Refine 2 commit 2: agent list plus real paging through offset."""

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


def test_agents_empty_then_lists_both(client):
    assert client.get("/agents").json() == {"agents": []}
    assert (
        client.post("/memory/add", json=make_place_payload(agent="robot-a")).status_code
        == 200
    )
    assert (
        client.post("/memory/add", json=make_place_payload(agent="robot-b")).status_code
        == 200
    )
    assert client.get("/agents").json() == {"agents": ["robot-a", "robot-b"]}


def test_list_pages_with_offset(client):
    for i in range(1, 6):
        assert (
            client.post(
                "/memory/add", json=make_place_payload(suffix=i, seed=i)
            ).status_code
            == 200
        )
    first = client.get("/memory/list", params={"agent_id": "robot-a", "limit": 2})
    assert first.status_code == 200
    body = first.json()
    assert body["total"] == 5
    assert len(body["places"]) == 2
    assert body["next_offset"] is not None
    second = client.get(
        "/memory/list",
        params={"agent_id": "robot-a", "limit": 2, "offset": body["next_offset"]},
    )
    assert second.status_code == 200
    assert len(second.json()["places"]) == 2


def test_list_walks_full_store(client):
    for i in range(1, 4):
        client.post("/memory/add", json=make_place_payload(suffix=i, seed=i))
    seen: list[str] = []
    offset = None
    for _ in range(5):
        params: dict = {"agent_id": "robot-a", "limit": 1}
        if offset is not None:
            params["offset"] = offset
        body = client.get("/memory/list", params=params).json()
        seen.extend([p["id"] for p in body["places"]])
        offset = body["next_offset"]
        if offset is None:
            break
    assert sorted(seen) == ["robot-a-1", "robot-a-2", "robot-a-3"]
