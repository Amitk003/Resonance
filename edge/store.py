"""Persistent offline local memory (Task 1 storage + Task 2 search).

Each robot gets an isolated Qdrant Local DB at:
    ./edge_data/<agent_id>/   collection: places

Runs in Qdrant local mode with no server and no network.
The Qdrant Edge binary comes later; this API stays the same.

No matching, alignment, scoring, sync, or API here.
Those build on top of this store in later tasks.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_OID, UUID, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    PointStruct,
    Range,
    VectorParams,
)

from edge.config import COLLECTION_NAME, DIM, agent_path
from edge.models import Payload, Place, Pose, validate_vector

logger = logging.getLogger(__name__)

# Project-specific namespace for point ids. Qdrant only accepts ints or
# UUIDs as point ids, so we derive one deterministic UUID per Place id.
# The original Place id stays in the payload as the public identifier.
_POINT_ID_NAMESPACE: UUID = uuid5(NAMESPACE_OID, "resonance.place.v1")


def _qdrant_point_id(place_id: str) -> str:
    """Map a Place id (e.g. 'robot-a-42') to a valid Qdrant point id."""
    return str(uuid5(_POINT_ID_NAMESPACE, place_id))


def _place_from_record(
    payload: dict[str, Any] | None,
    vector: Any,
    fallback_agent: str,
) -> Place | None:
    """Rebuild a Place from stored payload + vector, or None if corrupt."""
    if not payload or "id" not in payload:
        return None
    pose = payload.get("pose")
    if not isinstance(pose, dict):
        return None
    try:
        return Place(
            id=payload["id"],
            agent_id=payload.get("agent_id", fallback_agent),
            vector=list(vector) if vector is not None else [],
            pose=Pose(
                x=float(pose["x"]),
                y=float(pose["y"]),
                theta=float(pose["theta"]),
            ),
            timestamp=int(payload["timestamp"]),
            confidence=float(payload["confidence"]),
            payload=Payload(
                zone=str(payload.get("zone", "")),
                sensor=str(payload.get("sensor", "")),
                note=str(payload.get("note", "")),
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _place_payload(place: Place) -> dict:
    """Flatten a Place into the stored payload dict."""
    return {
        "id": place.id,
        "agent_id": place.agent_id,
        "pose": {"x": place.pose.x, "y": place.pose.y, "theta": place.pose.theta},
        "timestamp": place.timestamp,
        "confidence": place.confidence,
        "zone": place.payload.zone,
        "sensor": place.payload.sensor,
        "note": place.payload.note,
    }


# Task 5 owns filtering. When it lands, create payload indexes for these
# fields: confidence (float), timestamp (int), zone (keyword), sensor
# (keyword). Until then filters below stay correct, just unindexed.
SEARCH_INDEX_FIELDS: tuple[str, ...] = ("confidence", "timestamp", "zone", "sensor")


class PlaceStore:
    """Small storage abstraction around Qdrant Client local mode."""

    def __init__(self, agent_id: str, storage_root: Path | str | None = None) -> None:
        if not agent_id or not agent_id.strip():
            raise ValueError("agent_id must be non-empty")
        self.agent_id = agent_id
        self.storage_path: Path = agent_path(agent_id, root=storage_root)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.collection = COLLECTION_NAME
        # Local persistent mode - no server, no network.
        self._client = QdrantClient(path=str(self.storage_path))
        self.create_collection()

    # -- setup ---------------------------------------------------------
    def create_collection(self) -> None:
        """Create the collection (if missing) with 512-d cosine vectors."""
        if not self._client.collection_exists(self.collection):
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
            )

    def collection_info(self) -> dict:
        """Public read of collection shape: vector size, distance, points."""
        info = self._client.get_collection(self.collection)
        params = info.config.params.vectors
        return {
            "size": params.size,
            "distance": params.distance,
            "count": self.count(),
        }

    # -- public API ----------------------------------------------------
    def add(self, place: Place) -> str:
        """Upsert one Place. Same id overwrites (no duplicates)."""
        return self.add_many([place])[0]

    def add_many(self, places: list[Place]) -> list[str]:
        """Upsert many Places in one call. Same id overwrites."""
        points = []
        ids = []
        for place in places:
            if place.agent_id != self.agent_id:
                raise ValueError(
                    f"place agent_id '{place.agent_id}' "
                    f"does not match store '{self.agent_id}'"
                )
            points.append(
                PointStruct(
                    id=_qdrant_point_id(place.id),
                    vector=place.vector,
                    payload=_place_payload(place),
                )
            )
            ids.append(place.id)
        if points:
            self._client.upsert(collection_name=self.collection, points=points)
        return ids

    def get(self, place_id: str) -> Place | None:
        """Retrieve one Place by id, or None if missing or corrupt.

        Note: Qdrant COSINE stores L2-normalized vectors, so the returned
        vector keeps the direction but not the magnitude. Compare with
        cosine similarity, not raw values.
        """
        points = self._client.retrieve(
            collection_name=self.collection,
            ids=[_qdrant_point_id(place_id)],
            with_payload=True,
            with_vectors=True,
        )
        if not points:
            return None
        return _place_from_record(
            points[0].payload, points[0].vector, self.agent_id
        )

    def search(
        self,
        vector: list[float],
        top_k: int = 5,
        min_confidence: float = 0.0,
    ) -> list[tuple[Place, float]]:
        """Find nearest places by cosine similarity with confidence filter.

        Returns list of (Place, score) ordered by score descending.
        Corrupt records are skipped. Empty store returns [].
        Raises ValueError for bad vector, top_k, or min_confidence.
        """
        query = validate_vector(vector)
        if not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive int")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        query_filter = None
        if min_confidence > 0.0:
            # No payload index yet (Task 5 adds it); still correct.
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="confidence", range=Range(gte=min_confidence)
                    )
                ]
            )
        hits = self._client.search(
            collection_name=self.collection,
            query_vector=query,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=True,
        )
        results: list[tuple[Place, float]] = []
        for hit in hits:
            place = _place_from_record(hit.payload, hit.vector, self.agent_id)
            if place is not None:
                results.append((place, float(hit.score)))
        return results

    def count(self) -> int:
        """Number of stored places."""
        return self._client.count(collection_name=self.collection).count

    def clear(self) -> None:
        """Remove all places. Keeps the collection intact.

        Note: delete_collection + recreate does not reliably reset
        Qdrant 1.12 local mode, so we delete all points by id instead.
        """
        offset = None
        while True:
            points, offset = self._client.scroll(
                collection_name=self.collection, limit=256, offset=offset,
                with_payload=False, with_vectors=False,
            )
            if not points:
                break
            self._client.delete(
                collection_name=self.collection,
                points_selector=[pt.id for pt in points],
            )
            if offset is None:
                break

    def close(self) -> None:
        """Flush and release the local DB handle (needed for restart tests)."""
        try:
            self._client.close()
        except Exception as exc:
            logger.warning("Qdrant client did not close cleanly: %s", exc)
