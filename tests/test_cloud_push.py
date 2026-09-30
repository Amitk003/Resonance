"""Person 3 Task 15 tests - server link push, offline via :memory:."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from backend.app import create_app
from edge.cloud import CloudSync
from edge.store import PlaceStore
from tests.conftest import make_place


def test_push_new_places(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    cloud = CloudSync(client=QdrantClient(":memory:"))
    try:
        store.add_many([make_place(suffix=1, seed=1), make_place(suffix=2, seed=2)])
        places = [store.get("robot-a-1"), store.get("robot-a-2")]
        report = cloud.push_many([p for p in places if p is not None])
        assert report.uploaded == 2
        assert report.unchanged == 0
        assert report.conflicts == []
        assert cloud._read_server("robot-a-1") is not None
    finally:
        store.close()


def test_resend_same_is_unchanged(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    cloud = CloudSync(client=QdrantClient(":memory:"))
    try:
        place = make_place()
        store.add(place)
        first = cloud.push_many([place])
        second = cloud.push_many([place])
        assert (first.uploaded, first.unchanged) == (1, 0)
        assert (second.uploaded, second.unchanged) == (0, 1)
        assert second.conflicts == []
        assert cloud.conflict_history("robot-a-1") == []
    finally:
        store.close()


def test_conflict_winner_written_and_logged(tmp_path):
    cloud = CloudSync(client=QdrantClient(":memory:"))
    low = make_place(suffix=1, seed=1, confidence=0.4)
    high = make_place(suffix=1, seed=1, confidence=0.9)
    report = cloud.push_many([low])
    assert report.uploaded == 1
    report = cloud.push_many([high])
    assert report.uploaded == 1
    assert [log.reason for log in report.conflicts] == ["higher-confidence"]
    saved = cloud._read_server("robot-a-1")
    assert saved is not None
    assert saved.confidence == pytest.approx(0.9)
    history = cloud.conflict_history("robot-a-1")
    assert len(history) == 1
    assert history[0].confidence == pytest.approx(0.4)


def test_loser_stays_on_server(tmp_path):
    cloud = CloudSync(client=QdrantClient(":memory:"))
    high = make_place(suffix=1, seed=1, confidence=0.9)
    low = make_place(suffix=1, seed=1, confidence=0.2)
    cloud.push_many([high])
    report = cloud.push_many([low])
    assert [log.reason for log in report.conflicts] == ["higher-confidence"]
    saved = cloud._read_server("robot-a-1")
    assert saved is not None
    assert saved.confidence == pytest.approx(0.9)


def test_push_needs_client_or_url():
    with pytest.raises(ValueError):
        CloudSync()


@pytest.fixture
def client(tmp_path):
    app = create_app(storage_root=tmp_path)
    with TestClient(app) as c:
        yield c


def test_push_unreachable_server_returns_503(client):
    payload = {
        "id": "robot-a-1",
        "agent_id": "robot-a",
        "vector": make_place(suffix=1, seed=1).vector,
        "pose": {"x": 0.0, "y": 0.0, "theta": 0.0},
        "timestamp": 1,
        "confidence": 0.5,
        "payload": {"zone": "", "sensor": "", "note": ""},
    }
    assert client.post("/memory/add", json=payload).status_code == 200
    r = client.post(
        "/sync/push",
        json={"agent_id": "robot-a", "server_url": "http://127.0.0.1:9"},
    )
    assert r.status_code == 503


def test_push_bad_limit_rejected(client):
    r = client.post("/sync/push", json={"agent_id": "robot-a", "limit": 0})
    assert r.status_code == 422
