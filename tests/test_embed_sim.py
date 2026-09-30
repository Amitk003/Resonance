"""Refinement 1: hash embeddings plus drift sim plus full loop checks."""

from __future__ import annotations

import math

import pytest

from edge.align import estimate_transform
from edge.embed import HashEmbedder, get_embedder
from edge.match import cosine_score
from edge.models import Place
from edge.store import PlaceStore
from edge.sync import rank_places
from sim.make_drift import (
    TRUE_DTHETA,
    TRUE_DX,
    TRUE_DY,
    load_dataset,
    make_drift_dataset,
    save_dataset,
)


def test_hash_embed_dim_and_deterministic() -> None:
    embed = HashEmbedder()
    first = embed.encode_text("hall corner")
    second = embed.encode_text("hall corner")
    assert len(first) == 512
    assert first == second
    other = embed.encode_text("other place far away")
    assert cosine_score(first, other) < 0.5


def test_hash_embed_rejects_bad_input() -> None:
    embed = HashEmbedder()
    with pytest.raises(ValueError):
        embed.encode_text("")
    with pytest.raises(ValueError):
        embed.encode_image(b"")
    with pytest.raises(ValueError):
        get_embedder(mode="clip2")


def test_drift_dataset_shape() -> None:
    data = make_drift_dataset(n_shared=12, n_unique=2, seed=0)
    assert data["true_transform"] == {"dx": TRUE_DX, "dy": TRUE_DY, "dtheta": TRUE_DTHETA}
    assert len(data["robot_a"]) == 14
    assert len(data["robot_b"]) == 14
    assert data["robot_a"][0]["payload"]["note"] == "hazard spill"


def test_drift_save_load_roundtrip(tmp_path) -> None:
    data = make_drift_dataset(n_shared=6, n_unique=1, seed=1)
    path = save_dataset(data, tmp_path / "drift.json")
    back = load_dataset(path)
    assert back["shared"] == 6
    assert back["robot_a"][0]["id"] == "robot-a-1"


def _add_all(store: PlaceStore, rows: list[dict]) -> None:
    for row in rows:
        clean = {k: v for k, v in row.items() if k != "shared_index"}
        store.add(Place(**clean))


def test_full_loop_recall_transform_sync(tmp_path) -> None:
    data = make_drift_dataset(n_shared=12, n_unique=4, seed=0)
    store_a = PlaceStore(agent_id="robot-a", storage_root=tmp_path / "a")
    store_b = PlaceStore(agent_id="robot-b", storage_root=tmp_path / "b")
    try:
        _add_all(store_a, data["robot_a"])
        _add_all(store_b, data["robot_b"])

        # Match every B swap candidate against A memory with cosine.
        b_places, _ = store_b.list_places(limit=100)
        a_places, _ = store_a.list_places(limit=100)
        a_by_id = {p.id: p for p in a_places}
        b_shared = {r["id"]: f"robot-a-{r['shared_index'] + 1}" for r in data["robot_b"] if "shared_index" in r}

        correct = 0
        pairs: list[tuple[float, float, float, float]] = []
        for b in b_places:
            if b.id not in b_shared:
                continue
            best_id = max(a_places, key=lambda a: cosine_score(b.vector, a.vector)).id
            if best_id == b_shared[b.id]:
                correct += 1
                a = a_by_id[best_id]
                pairs.append((a.pose.x, a.pose.y, b.pose.x, b.pose.y))

        recall = correct / len(b_shared)
        assert recall >= 0.8

        # Align B into A. Sim applies A->B drift, so expected is inverse.
        est = estimate_transform(pairs)
        assert est is not None
        c, s = math.cos(TRUE_DTHETA), math.sin(TRUE_DTHETA)
        exp_dx = -c * TRUE_DX - s * TRUE_DY
        exp_dy = s * TRUE_DX - c * TRUE_DY
        exp_dt = -TRUE_DTHETA
        assert abs(est.dx - exp_dx) < 0.3
        assert abs(est.dy - exp_dy) < 0.3
        angle_err = abs((est.dtheta - exp_dt + math.pi) % (2 * math.pi) - math.pi)
        assert angle_err < math.radians(5)

        # Sync sends hazards first.
        ranked = rank_places(a_places)
        assert "hazard" in ranked[0][2]
    finally:
        store_a.close()
        store_b.close()
