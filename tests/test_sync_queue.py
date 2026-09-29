"""Person 3 Task 7 tests - upload order ranking, fully offline."""

from __future__ import annotations

import pytest

from edge.store import PlaceStore
from edge.sync import rank_places, select_upload, value_score
from tests.conftest import make_place


def test_hazard_first_despite_low_confidence():
    low_hazard = make_place(suffix=1, seed=1, confidence=0.1)
    low_hazard.payload.note = "hazard: gas leak"
    plain = make_place(suffix=2, seed=2, confidence=0.99)
    ranked = rank_places([plain, low_hazard])
    assert [p.id for p, _, _ in ranked] == ["robot-a-1", "robot-a-2"]
    assert ranked[0][2] == ["hazard"]


def test_anchor_beats_plain():
    anchor = make_place(suffix=1, seed=1, confidence=0.5)
    plain = make_place(suffix=2, seed=2, confidence=0.9)
    ranked = rank_places([plain, anchor], anchors=frozenset({"robot-a-1"}))
    assert [p.id for p, _, _ in ranked] == ["robot-a-1", "robot-a-2"]
    assert "anchor" in ranked[0][2]


def test_confidence_orders_normals():
    places = [make_place(suffix=i, seed=i, confidence=0.1 * i) for i in (1, 2, 3)]
    ranked = rank_places(places)
    assert [p.id for p, _, _ in ranked] == ["robot-a-3", "robot-a-2", "robot-a-1"]


def test_rare_zone_outranks_common_zone():
    common_a = make_place(suffix=1, seed=1, confidence=0.8)
    common_b = make_place(suffix=2, seed=2, confidence=0.8)
    lone = make_place(suffix=3, seed=3, confidence=0.8)
    lone.payload.zone = "vault"
    ranked = rank_places([common_a, common_b, lone])
    assert ranked[0][0].id == "robot-a-3"
    assert "rare" in ranked[0][2]


def test_score_stays_in_range():
    place = make_place(confidence=1.0)
    place.payload.note = "hazard"
    score, _ = value_score(place, zone_share=0.0, anchor=True)
    assert score == pytest.approx(1.0)


def test_select_upload_empty(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        assert select_upload(store) == []
    finally:
        store.close()


def test_select_upload_order_and_limit(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        for i in range(1, 6):
            store.add(make_place(suffix=i, seed=i, confidence=0.1 * i))
        hz = make_place(suffix=9, seed=9, confidence=0.1)
        hz.payload.note = "hazard"
        store.add(hz)
        got = select_upload(store, limit=3)
        assert [p.id for p, _, _ in got] == ["robot-a-9", "robot-a-5", "robot-a-4"]
    finally:
        store.close()


def test_select_upload_bad_limit(tmp_path):
    store = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    try:
        with pytest.raises(ValueError):
            select_upload(store, limit=0)
        with pytest.raises(ValueError):
            select_upload(store, limit=101)
    finally:
        store.close()
