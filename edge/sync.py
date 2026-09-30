"""Upload order for cloud sync (Task 7, ranking only).

Scores each local place from 0 to 1 and returns them best first, so
the sync layer always sends hazards first and filler last. No network
and no server push here. Task 11 owns conflicts, Task 15 owns upload,
Task 14 owns the HTTP endpoint. This module is pure logic plus a thin
store reader, fully offline and unit tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from edge.models import HAZARD_KEYWORD, Place

if TYPE_CHECKING:
    from edge.store import PlaceStore

import numpy as _np

# Score weights. They add up to 1.0 so the result stays in [0, 1].
HAZARD_WEIGHT: float = 0.4
ANCHOR_WEIGHT: float = 0.3
CONFIDENCE_WEIGHT: float = 0.2
RARITY_WEIGHT: float = 0.1


def value_score(
    place: Place,
    zone_share: float = 0.0,
    anchor: bool = False,
) -> tuple[float, list[str]]:
    """Score one place plus the reasons why. Higher means upload first.

    zone_share is how common the place zone is in the candidate set
    (0 = unique, 1 = everything shares it). anchor marks places that
    helped align maps; Task 13 will feed those in, until then False.
    """
    score = 0.0
    reasons: list[str] = []
    if HAZARD_KEYWORD in place.payload.note.lower():
        score += HAZARD_WEIGHT
        reasons.append("hazard")
    if anchor:
        score += ANCHOR_WEIGHT
        reasons.append("anchor")
    score += CONFIDENCE_WEIGHT * place.confidence
    rarity = max(0.0, min(1.0, 1.0 - zone_share))
    score += RARITY_WEIGHT * rarity
    if rarity >= 0.5:
        reasons.append("rare")
    return round(score, 4), reasons


def rank_places(
    places: list[Place],
    anchors: frozenset[str] = frozenset(),
) -> list[tuple[Place, float, list[str]]]:
    """Order places best first. Ties break toward newer timestamps.

    Rarity is measured inside the given set: a zone seen once counts
    as fully rare, a zone on every place counts as fully common.
    """
    zone_counts: dict[str, int] = {}
    for place in places:
        zone_counts[place.payload.zone] = zone_counts.get(place.payload.zone, 0) + 1
    total = len(places) or 1
    scored = []
    for place in places:
        share = zone_counts[place.payload.zone] / total
        score, reasons = value_score(
            place, zone_share=share, anchor=place.id in anchors
        )
        scored.append((place, score, reasons, place.timestamp))
    scored.sort(key=lambda row: (row[1], row[3]), reverse=True)
    return [(place, score, reasons) for place, score, reasons, _ in scored]


def select_upload(
    store: PlaceStore,
    limit: int = 20,
    anchors: frozenset[str] = frozenset(),
) -> list[tuple[Place, float, list[str]]]:
    """Top ranked places from one agent store, best first."""
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= 100
    ):
        raise ValueError("limit must be an int in [1, 100]")
    return rank_places(store.iter_all(page_size=256), anchors=anchors)[:limit]


def vectors_same(a: list[float], b: list[float], tol: float = 1e-4) -> bool:
    """Direction match tolerant to Qdrant float32 normalize roundtrips."""
    va = _np.array(a, dtype=float)
    vb = _np.array(b, dtype=float)
    na = float(_np.linalg.norm(va))
    nb = float(_np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return list(a) == list(b)
    return float(va @ vb / (na * nb)) >= 1.0 - tol


# -- Task 11: conflicts + version history -------------------------------

HISTORY_LIMIT: int = 10


@dataclass
class ConflictLog:
    """One conflict decision for the dashboard log (Task 14 exposes it)."""

    id: str
    winner_id: str
    loser_id: str
    reason: str


def _same_place(a: Place, b: Place) -> bool:
    return (
        a.confidence == b.confidence
        and a.timestamp == b.timestamp
        and a.pose == b.pose
        and a.payload == b.payload
        and vectors_same(list(a.vector), list(b.vector))
    )


def resolve_conflict(
    existing: Place,
    incoming: Place,
    votes_existing: int = 1,
    votes_incoming: int = 1,
    history: dict[str, list[Place]] | None = None,
) -> tuple[Place, ConflictLog]:
    """Pick a winner for one id, keep the loser in history, never drop data.

    Rules (docs/sync-policy.md): higher confidence wins, tie goes to
    more agent votes, then newer timestamp, then keep existing.
    Identical resends return existing with reason "same" and no history.
    """
    if existing.id != incoming.id:
        raise ValueError("conflict must share one place id")
    for name, votes in (("votes_existing", votes_existing), ("votes_incoming", votes_incoming)):
        if not isinstance(votes, int) or isinstance(votes, bool) or votes < 1:
            raise ValueError(f"{name} must be an int >= 1")
    if _same_place(existing, incoming):
        return existing, ConflictLog(existing.id, existing.id, incoming.id, "same")
    if incoming.confidence != existing.confidence:
        winner = incoming if incoming.confidence > existing.confidence else existing
        reason = "higher-confidence"
    elif votes_incoming != votes_existing:
        winner = incoming if votes_incoming > votes_existing else existing
        reason = "more-votes"
    elif incoming.timestamp != existing.timestamp:
        winner = incoming if incoming.timestamp > existing.timestamp else existing
        reason = "newer"
    else:
        winner, reason = existing, "tie-keep-existing"
    loser = incoming if winner is existing else existing
    if history is not None:
        versions = history.setdefault(existing.id, [])
        versions.append(loser)
        del versions[: max(0, len(versions) - HISTORY_LIMIT)]
    return winner, ConflictLog(existing.id, winner.id, loser.id, reason)
