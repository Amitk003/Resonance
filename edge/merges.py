"""Meeting runs plus merge history (Task 12, no fuse gate).

run_meeting takes two agent stores, matches B's swap set against A's
memory, fits the rigid transform, and scores the result. The score
blends mean vector match with shape fit. Deciding fuse vs log from
the score belongs to Task 13, not here.

MergeLog keeps finished meetings in one JSON file newest handling
done by the reader. Fully offline.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from edge.align import estimate_transform
from edge.config import EDGE_DATA_ROOT
from edge.match import find_matches
from edge.models import MergeRecord, Place, Transform

if TYPE_CHECKING:
    from edge.store import PlaceStore

# Cap so the history file stays small forever.
HISTORY_LIMIT: int = 200


def run_meeting(
    store_a: PlaceStore,
    store_b: PlaceStore,
    swap_limit: int = 20,
    top_k: int = 1,
    min_score: float = 0.0,
    inlier_thresh: float = 0.5,
) -> MergeRecord | None:
    """Run one meeting: B's swap set against A's memory.

    Returns a scored MergeRecord, or None when fewer than 2 pairs
    match or the shape check finds no consensus.
    """
    swap = store_b.pick_swap(limit=swap_limit)
    if not swap:
        return None
    places_a: list[Place] = []
    offset = None
    while True:
        page, offset = store_a.list_places(limit=256, offset=offset)
        places_a.extend(page)
        if offset is None:
            break
    matches = find_matches(places_a, swap, top_k=top_k, min_score=min_score)
    if len(matches) < 2:
        return None
    pose_a = {place.id: place.pose for place in places_a}
    pose_b = {cand.id: cand.pose for cand in swap}
    pairs = []
    for match in matches:
        pa = pose_a.get(match.match_id)
        pb = pose_b.get(match.query_id)
        if pa is None or pb is None:
            continue
        pairs.append((pa.x, pa.y, pb.x, pb.y))
    if len(pairs) < 2:
        return None
    estimate = estimate_transform(pairs, inlier_thresh=inlier_thresh)
    if estimate is None:
        return None
    mean_score = sum(match.score for match in matches) / len(matches)
    shape_fit = estimate.shape_fit
    return MergeRecord(
        id=uuid4().hex[:12],
        timestamp=int(time.time()),
        agent_a=store_a.agent_id,
        agent_b=store_b.agent_id,
        pairs_total=len(pairs),
        inliers=estimate.inliers,
        mean_score=round(mean_score, 4),
        score=round(max(0.0, min(1.0, mean_score * shape_fit)), 4),
        transform=Transform(
            dx=estimate.dx, dy=estimate.dy, dtheta=estimate.dtheta
        ),
    )


class MergeLog:
    """JSON file log of finished meetings, newest first on read."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else EDGE_DATA_ROOT / "merges.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> list[MergeRecord]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        records = []
        for item in raw if isinstance(raw, list) else []:
            try:
                records.append(MergeRecord(**item))
            except ValueError:
                continue
        return records

    def _write_all(self, records: list[MergeRecord]) -> None:
        text = json.dumps([record.model_dump() for record in records], indent=1)
        self.path.write_text(text, encoding="utf-8")

    def append(self, record: MergeRecord) -> MergeRecord:
        """Add one record, oldest drop past the cap. Returns the record."""
        records = self._read_all()
        records.append(record)
        self._write_all(records[-HISTORY_LIMIT:])
        return record

    def list(self, limit: int = 50) -> list[MergeRecord]:
        """Newest first, at most limit records."""
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 200
        ):
            raise ValueError("limit must be an int in [1, 200]")
        return self._read_all()[::-1][:limit]

    def clear(self) -> None:
        """Remove all records. Used by tests."""
        self._write_all([])
