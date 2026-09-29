"""Task 9 tests - nearest neighbor match between two agents.

Pure cosine checks plus the store bridge, all fully offline.
Run: pytest -v
"""

from __future__ import annotations

import pytest

from edge.match import cosine_score, find_matches, match_agents
from edge.models import place_to_swap_candidate
from edge.store import PlaceStore
from tests.conftest import make_place, make_vector


def candidate(agent: str = "robot-b", suffix: int = 7, seed: int = 2):
    return place_to_swap_candidate(make_place(agent=agent, suffix=suffix, seed=seed))


def test_cosine_identical():
    assert cosine_score(make_vector(1), make_vector(1)) == pytest.approx(1.0)


def test_cosine_orthogonal_and_opposite():
    assert cosine_score([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_score([1.0, 1.0], [-1.0, -1.0]) == pytest.approx(-1.0)


def test_cosine_zero_vector():
    assert cosine_score([0.0] * 8, [1.0] * 8) == 0.0
    assert cosine_score([1.0] * 8, [0.0] * 8) == 0.0


def test_find_matches_shared_place():
    own = [make_place(agent="robot-a", suffix=i, seed=i) for i in (1, 2, 3)]
    got = find_matches(own, [candidate(seed=2)])
    assert len(got) == 1
    m = got[0]
    assert m.query_id == "robot-b-7"
    assert m.match_id == "robot-a-2"
    assert m.score == pytest.approx(1.0)
    assert m.pair_id == "robot-b-7~robot-a-2"
    assert m.inliers == 0


def test_find_matches_top_k_order():
    own = [make_place(agent="robot-a", suffix=i, seed=i) for i in (1, 2, 3)]
    got = find_matches(own, [candidate(seed=1)], top_k=2)
    assert len(got) == 2
    assert got[0].match_id == "robot-a-1"
    assert got[0].score >= got[1].score


def test_find_matches_min_score_cutoff():
    own = [make_place(agent="robot-a", suffix=i, seed=i) for i in (1, 2, 3)]
    assert find_matches(own, [candidate(seed=1)], min_score=0.999) != []
    assert find_matches(own, [candidate(seed=9)], min_score=0.999) == []


def test_find_matches_empty_inputs():
    own = [make_place(suffix=1, seed=1)]
    assert find_matches([], [candidate()]) == []
    assert find_matches(own, []) == []
    assert find_matches([], []) == []


def test_find_matches_bad_args():
    own = [make_place(suffix=1, seed=1)]
    other = [candidate()]
    for bad in (0, -1, True, "2"):
        with pytest.raises(ValueError):
            find_matches(own, other, top_k=bad)  # type: ignore[arg-type]
    for bad in (-2.0, 2.0, "0.5", True):
        with pytest.raises(ValueError):
            find_matches(own, other, min_score=bad)  # type: ignore[arg-type]


def test_find_matches_tie_break_stable():
    a = make_place(agent="robot-a", suffix=2, seed=5)
    b = make_place(agent="robot-a", suffix=1, seed=5)
    got = find_matches([a, b], [candidate(seed=5)], top_k=2)
    assert [m.match_id for m in got] == ["robot-a-1", "robot-a-2"]


def test_match_agents_shared_place(tmp_path):
    a = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    b = PlaceStore(agent_id="robot-b", storage_root=tmp_path)
    try:
        for i in (1, 2, 3):
            a.add(make_place(agent="robot-a", suffix=i, seed=i))
        b.add(make_place(agent="robot-b", suffix=2, seed=2))
        b.add(make_place(agent="robot-b", suffix=9, seed=9))
        got = match_agents(a, b, swap_limit=10)
        assert len(got) == 2
        shared = [m for m in got if m.query_id == "robot-b-2"]
        assert len(shared) == 1
        assert shared[0].match_id == "robot-a-2"
        assert shared[0].score == pytest.approx(1.0)
    finally:
        a.close()
        b.close()


def test_match_agents_empty_other(tmp_path):
    a = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    b = PlaceStore(agent_id="robot-b", storage_root=tmp_path)
    try:
        a.add(make_place(agent="robot-a", suffix=1, seed=1))
        assert match_agents(a, b) == []
    finally:
        a.close()
        b.close()


def test_match_agents_bad_swap_limit(tmp_path):
    a = PlaceStore(agent_id="robot-a", storage_root=tmp_path)
    b = PlaceStore(agent_id="robot-b", storage_root=tmp_path)
    try:
        with pytest.raises(ValueError):
            match_agents(a, b, swap_limit=0)
        with pytest.raises(ValueError):
            match_agents(a, b, swap_limit=101)
    finally:
        a.close()
        b.close()
