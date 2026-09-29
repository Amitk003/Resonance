"""Task 5 tests - offline vector search with filters.

Covers zone, sensor, and timestamp filters at the store level plus
the matching API fields. All offline, no server, no model downloads.
Run: pytest -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from edge.models import Place
from edge.store import PlaceStore
from tests.conftest import make_place_payload, make_vector


def seed_store(tmp_path) -> PlaceStore:
    """Three places with distinct zone, sensor, time, and confidence."""
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    spots = [
        ("hall", "cam", 100, 0.9, 1),
        ("lab", "lidar", 200, 0.8, 2),
        ("hall", "lidar", 300, 0.4, 3),
    ]
    for i, (zone, sensor, ts, conf, seed) in enumerate(spots, start=1):
        store.add(
            Place(
                id=f"robot-a-{i}",
                agent_id="robot-a",
                vector=make_vector(seed),
                pose={"x": float(i), "y": 2.0, "theta": 0.1},
                timestamp=ts,
                confidence=conf,
                payload={"zone": zone, "sensor": sensor, "note": ""},
            )
        )
    return store


def query_of(store: PlaceStore, place_id: str) -> list[float]:
    saved = store.get(place_id)
    assert saved is not None
    return saved.vector


def test_zone_filter(tmp_path):
    store = seed_store(tmp_path)
    try:
        hits = store.search(query_of(store, "robot-a-1"), top_k=5, zones=["hall"])
        assert [p.id for p, _ in hits] == ["robot-a-1", "robot-a-3"]
        hits = store.search(query_of(store, "robot-a-1"), top_k=5, zones=["lab"])
        assert [p.id for p, _ in hits] == ["robot-a-2"]
    finally:
        store.close()


def test_zone_filter_multi(tmp_path):
    store = seed_store(tmp_path)
    try:
        hits = store.search(
            query_of(store, "robot-a-1"), top_k=5, zones=["hall", "lab"]
        )
        assert len(hits) == 3
    finally:
        store.close()


def test_sensor_filter(tmp_path):
    store = seed_store(tmp_path)
    try:
        hits = store.search(query_of(store, "robot-a-2"), top_k=5, sensors=["lidar"])
        assert [p.id for p, _ in hits] == ["robot-a-2", "robot-a-3"]
    finally:
        store.close()


def test_time_window(tmp_path):
    store = seed_store(tmp_path)
    try:
        hits = store.search(query_of(store, "robot-a-1"), top_k=5, since=150, until=250)
        assert [p.id for p, _ in hits] == ["robot-a-2"]
        hits = store.search(query_of(store, "robot-a-1"), top_k=5, since=250)
        assert [p.id for p, _ in hits] == ["robot-a-3"]
        hits = store.search(query_of(store, "robot-a-1"), top_k=5, until=150)
        assert [p.id for p, _ in hits] == ["robot-a-1"]
    finally:
        store.close()


def test_combined_filters(tmp_path):
    store = seed_store(tmp_path)
    try:
        hits = store.search(
            query_of(store, "robot-a-1"),
            top_k=5,
            zones=["hall"],
            sensors=["lidar"],
            min_confidence=0.3,
        )
        assert [p.id for p, _ in hits] == ["robot-a-3"]
        hits = store.search(
            query_of(store, "robot-a-1"),
            top_k=5,
            zones=["hall"],
            min_confidence=0.5,
        )
        assert [p.id for p, _ in hits] == ["robot-a-1"]
    finally:
        store.close()


def test_no_match_returns_empty(tmp_path):
    store = seed_store(tmp_path)
    try:
        assert store.search(query_of(store, "robot-a-1"), zones=["nowhere"]) == []
        assert store.search(query_of(store, "robot-a-1"), since=9999) == []
    finally:
        store.close()


def test_none_and_empty_means_no_filter(tmp_path):
    store = seed_store(tmp_path)
    try:
        plain = [p.id for p, _ in store.search(query_of(store, "robot-a-1"), top_k=5)]
        assert len(plain) == 3
        # Scores can differ in the last float digits between calls,
        # so compare ids only.
        assert [
            p.id
            for p, _ in store.search(query_of(store, "robot-a-1"), top_k=5, zones=None)
        ] == plain
        assert [
            p.id
            for p, _ in store.search(query_of(store, "robot-a-1"), top_k=5, zones=[])
        ] == plain
        assert [
            p.id
            for p, _ in store.search(query_of(store, "robot-a-1"), top_k=5, sensors=[])
        ] == plain
    finally:
        store.close()


def test_invalid_filters_raise(tmp_path):
    store = seed_store(tmp_path)
    try:
        q = query_of(store, "robot-a-1")
        with pytest.raises(ValueError):
            store.search(q, zones="hall")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            store.search(q, zones=[""])
        with pytest.raises(ValueError):
            store.search(q, sensors=[1])  # type: ignore[list-item]
        with pytest.raises(ValueError):
            store.search(q, since=-1)
        with pytest.raises(ValueError):
            store.search(q, until=True)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            store.search(q, since=300, until=100)
    finally:
        store.close()


def test_indexes_idempotent_and_reopen(tmp_path):
    store = seed_store(tmp_path)
    try:
        store.ensure_payload_indexes()
        store.ensure_payload_indexes()
        assert len(store.search(query_of(store, "robot-a-1"), zones=["hall"])) == 2
    finally:
        store.close()
    reopened = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        assert (
            len(reopened.search(query_of(reopened, "robot-a-1"), zones=["hall"])) == 2
        )
    finally:
        reopened.close()


@pytest.fixture
def client(tmp_path):
    app = create_app(storage_root=tmp_path)
    with TestClient(app) as c:
        yield c


def seed_api(client, agent: str = "robot-a") -> None:
    spots = [
        ("hall", "cam", 100, 0.9, 1),
        ("lab", "lidar", 200, 0.8, 2),
        ("hall", "lidar", 300, 0.4, 3),
    ]
    for i, (zone, sensor, ts, conf, seed) in enumerate(spots, start=1):
        payload = make_place_payload(agent=agent, suffix=i, seed=seed, confidence=conf)
        payload["timestamp"] = ts
        payload["payload"] = {"zone": zone, "sensor": sensor, "note": ""}
        assert client.post("/memory/add", json=payload).status_code == 200


def search_api(client, **kwargs):
    body = {"agent_id": "robot-a", "vector": make_vector(1), "top_k": 5}
    body.update(kwargs)
    return client.post("/memory/search", json=body)


def test_api_zone_filter(client):
    seed_api(client)
    r = search_api(client, zones=["hall"])
    assert r.status_code == 200, r.text
    assert [h["id"] for h in r.json()] == ["robot-a-1", "robot-a-3"]


def test_api_sensor_and_time_filter(client):
    seed_api(client)
    r = search_api(client, sensors=["lidar"])
    assert r.status_code == 200, r.text
    assert sorted(h["id"] for h in r.json()) == ["robot-a-2", "robot-a-3"]
    r = search_api(client, since=150, until=250)
    assert r.status_code == 200, r.text
    assert [h["id"] for h in r.json()] == ["robot-a-2"]


def test_api_combined_with_confidence(client):
    seed_api(client)
    r = search_api(client, zones=["hall"], min_confidence=0.5)
    assert r.status_code == 200, r.text
    assert [h["id"] for h in r.json()] == ["robot-a-1"]


def test_api_bad_range_rejected(client):
    seed_api(client)
    r = search_api(client, since=300, until=100)
    assert r.status_code == 422
    r = search_api(client, zones=[""])
    assert r.status_code == 422
