"""Nearest neighbor match between two agents (Task 9, vector score only).

Compares one robot's swap set against another robot's memory with
cosine similarity. Pure numpy logic, fully offline. No shape check,
no transform, no sync, no HTTP here. Task 10 owns the shape check,
Task 14 owns the endpoint.
"""

from __future__ import annotations

import numpy as np

from edge.models import Place, PlaceMatch, SwapCandidate, make_pair_id


def cosine_score(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]. A zero vector has no direction."""
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(max(-1.0, min(1.0, float(va @ vb) / (na * nb))))


def find_matches(
    own_places: list[Place],
    other: list[SwapCandidate],
    top_k: int = 1,
    min_score: float = 0.0,
) -> list[PlaceMatch]:
    """Match each swapped candidate against own memory.

    Queries come from `other`, matches from `own_places`. Each query
    keeps its top_k own places at or above min_score, best first.
    Ties break toward the smaller match id so runs are stable.
    Empty inputs return []. Raises ValueError for bad top_k or
    min_score.
    """
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError("top_k must be a positive int")
    if (
        not isinstance(min_score, (int, float))
        or isinstance(min_score, bool)
        or not -1.0 <= min_score <= 1.0
    ):
        raise ValueError("min_score must be in [-1, 1]")
    matches: list[PlaceMatch] = []
    for cand in other:
        scored = [(cosine_score(cand.vector, place.vector), place) for place in own_places]
        scored.sort(key=lambda row: (-row[0], row[1].id))
        for score, place in scored[:top_k]:
            if score < min_score:
                break
            matches.append(
                PlaceMatch(
                    pair_id=make_pair_id(cand.id, place.id),
                    query_id=cand.id,
                    match_id=place.id,
                    score=round(score, 6),
                )
            )
    return matches
