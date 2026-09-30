"""Person 4 Task 12 tests - meeting run plus merge history, offline."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from edge.merges import MergeLog, run_meeting
from edge.store import PlaceStore
from tests.conftest import make_place


def seed_pair(tmp_path, dx=2.0, dy=-1.0):
    """Two stores sharing 3 vectors, B shifted by (dx, dy), no rotation."""
    a = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    b = PlaceStore(agent_id="robot-b", storage_root=tmp_path)
    spots = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    for i, (x, y) in enumerate(spots, start=1):
        pa = make_place(agent="robot-a", suffix=i, seed=i)
        pa.pose.x = x
        pa.pose.y = y
        a.add(pa)
        pb = make_place(agent="robot-b", suffix=i, seed=i)
        pb.pose.x = x + dx
        pb.pose.y = y + dy
        b.add(pb)
    return a, b


def test_run_meeting_finds_shift(tmp_path):
    a, b = seed_pair(tmp_path)
    try:
        record = run_meeting(a, b)
        assert record is not None
        assert record.agent_a == "robot-a"
        assert record.agent_b == "robot-b"
        assert record.pairs_total == 3
        assert record.inliers == 3
        assert record.score == pytest.approx(1.0)
        assert record.transform.dx == pytest.approx(-2.0, abs=1e-6)
        assert record.transform.dy == pytest.approx(1.0, abs=1e-6)
        assert record.transform.dtheta == pytest.approx(0.0, abs=1e-6)
    finally:
        a.close()
        b.close()


def test_run_meeting_no_overlap_returns_none(tmp_path):
    a = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    b = PlaceStore(agent_id="robot-b", storage_root=tmp_path)
    try:
        a.add(make_place(agent="robot-a", suffix=1, seed=1))
        assert run_meeting(a, b) is None
    finally:
        a.close()
        b.close()


def test_merge_log_roundtrip_and_cap(tmp_path):
    log = MergeLog(tmp_path / "merges.json")
    a, b = seed_pair(tmp_path / "stores")
    try:
        record = run_meeting(a, b)
        assert record is not None
        log.append(record)
        listed = log.list()
        assert len(listed) == 1
        assert listed[0].id == record.id
        log.clear()
        assert log.list() == []
    finally:
        a.close()
        b.close()


@pytest.fixture
def client(tmp_path):
    app = create_app(storage_root=tmp_path)
    with TestClient(app) as c:
        yield c


def test_align_api_and_history(client):
    for agent in ("robot-a", "robot-b"):
        for i, (x, y) in enumerate([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], start=1):
            payload = {
                "id": f"{agent}-{i}",
                "agent_id": agent,
                "vector": make_place(agent=agent, suffix=i, seed=i).vector,
                "pose": {
                    "x": x + (2.0 if agent == "robot-b" else 0.0),
                    "y": y + (-1.0 if agent == "robot-b" else 0.0),
                    "theta": 0.0,
                },
                "timestamp": 1727000000,
                "confidence": 0.9,
                "payload": {"zone": "hall", "sensor": "cam", "note": ""},
            }
            assert client.post("/memory/add", json=payload).status_code == 200
    r = client.post("/meet/align", json={"agent_a": "robot-a", "agent_b": "robot-b"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score"] == pytest.approx(1.0)
    assert body["transform"]["dx"] == pytest.approx(-2.0, abs=1e-4)
    h = client.get("/merges")
    assert h.status_code == 200
    assert len(h.json()) == 1
    assert h.json()[0]["id"] == body["id"]


def test_align_api_same_agent_rejected(client):
    r = client.post("/meet/align", json={"agent_a": "robot-a", "agent_b": "robot-a"})
    assert r.status_code == 422


def test_align_api_no_consensus_returns_400(client):
    payload = {
        "id": "robot-a-1",
        "agent_id": "robot-a",
        "vector": make_place(agent="robot-a", suffix=1, seed=1).vector,
        "pose": {"x": 0.0, "y": 0.0, "theta": 0.0},
        "timestamp": 1727000000,
        "confidence": 0.9,
        "payload": {"zone": "", "sensor": "", "note": ""},
    }
    assert client.post("/memory/add", json=payload).status_code == 200
    r = client.post("/meet/align", json={"agent_a": "robot-a", "agent_b": "robot-b"})
    assert r.status_code == 400
