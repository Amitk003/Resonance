"""Upload order for cloud sync (Task 7, ranking only).

Scores each local place from 0 to 1 and returns them best first, so
the sync layer always sends hazards first and filler last. No network
and no server push here. Task 11 owns conflicts, Task 15 owns upload,
Task 14 owns the HTTP endpoint. This module is pure logic plus a thin
store reader, fully offline and unit tested.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from edge.models import HAZARD_KEYWORD, Place

if TYPE_CHECKING:
    from edge.store import PlaceStore

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
    """Top ranked places from one agent store, best first.

    Reads the whole local store through pages, ranks in memory, and
    returns at most limit entries. Same O(n) tradeoff as pick_swap,
    recorded there; fine for edge stores.
    """
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= 100
    ):
        raise ValueError("limit must be an int in [1, 100]")
    places: list[Place] = []
    offset = None
    while True:
        page, offset = store.list_places(limit=256, offset=offset)
        places.extend(page)
        if offset is None:
            break
    return rank_places(places, anchors=anchors)[:limit]
