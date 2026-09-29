"""Task 11 tests — conflict winner plus history, fully offline."""

from __future__ import annotations

import pytest

from edge.sync import HISTORY_LIMIT, resolve_conflict
from tests.conftest import make_place


def test_higher_confidence_wins_and_history():
    old = make_place(suffix=5, seed=5, confidence=0.6)
    new = make_place(suffix=5, seed=6, confidence=0.9)
    history: dict = {}
    winner, log = resolve_conflict(old, new, history=history)
    assert winner.confidence == pytest.approx(0.9)
    assert log.reason == "higher-confidence"
    assert [p.confidence for p in history["robot-a-5"]] == [pytest.approx(0.6)]


def test_tie_goes_to_more_votes():
    old = make_place(suffix=5, seed=5, confidence=0.8)
    new = make_place(suffix=5, seed=6, confidence=0.8)
    winner, log = resolve_conflict(old, new, votes_existing=2, votes_incoming=1)
    assert winner is old
    assert log.reason == "more-votes"


def test_newer_wins_on_full_tie():
    old = make_place(suffix=5, seed=5, confidence=0.8)
    new = make_place(suffix=5, seed=6, confidence=0.8)
    new.timestamp = old.timestamp + 10
    winner, log = resolve_conflict(old, new, history={})
    assert winner is new
    assert log.reason == "newer"


def test_identical_resend_keeps_history_empty():
    old = make_place(suffix=5, seed=5, confidence=0.8)
    history: dict = {}
    winner, log = resolve_conflict(old, old.model_copy(deep=True), history=history)
    assert log.reason == "same"
    assert history == {}


def test_history_order_and_cap():
    history: dict = {}
    base = make_place(suffix=5, seed=1, confidence=0.1)
    for i in range(HISTORY_LIMIT + 3):
        incoming = make_place(suffix=5, seed=i + 2, confidence=0.1 + 0.01 * (i + 1))
        base, _ = resolve_conflict(base, incoming, history=history)
    versions = history["robot-a-5"]
    assert len(versions) == HISTORY_LIMIT
    assert versions[-1].confidence > versions[0].confidence


def test_mismatched_ids_rejected():
    with pytest.raises(ValueError):
        resolve_conflict(make_place(suffix=1), make_place(suffix=2))
