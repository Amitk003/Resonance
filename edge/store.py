"""Persistent offline local memory (Task 1, storage-only).

Each robot gets an isolated Qdrant Local DB at:
    ./edge_data/<agent_id>/   collection: places

No search, matching, alignment, scoring, sync, or API here.
Those build on top of this store in later tasks.
"""

from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from edge.config import COLLECTION_NAME, DIM, agent_path
from edge.models import Payload, Place, Pose

# Fields Task 5 filtering will need — indexes created now, logic later.
_INDEX_FIELDS: dict[str, PayloadSchemaType] = {
    "agent_id": PayloadSchemaType.KEYWORD,
    "timestamp": PayloadSchemaType.INTEGER,
    "confidence": PayloadSchemaType.FLOAT,
    "zone": PayloadSchemaType.KEYWORD,
    "sensor": PayloadSchemaType.KEYWORD,
}


def _qdrant_point_id(place_id: str) -> str:
    """Map a Place id (e.g. 'robot-a-42') to a valid Qdrant point id.

    Qdrant only accepts ints or UUIDs as point ids, so we derive a
    deterministic UUID5. The original Place id is kept in the payload
    and used as the public identifier.
    """
    return str(uuid5(NAMESPACE_URL, place_id))


class PlaceStore:
    """Small storage abstraction around Qdrant Client local mode."""

    def __init__(self, agent_id: str, storage_root: Path | str | None = None) -> None:
        if not agent_id or not agent_id.strip():
            raise ValueError("agent_id must be non-empty")
        self.agent_id = agent_id
        self.storage_path: Path = agent_path(agent_id, root=storage_root)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.collection = COLLECTION_NAME
        # Local persistent mode — no server, no network.
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
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        for field, schema in _INDEX_FIELDS.items():
            try:
                self._client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field,
                    field_schema=schema,
                )
            except (UnexpectedResponse, ValueError, Exception):
                # Index already exists — safe to ignore for idempotency.
                continue

    # -- public API ----------------------------------------------------
    def add(self, place: Place) -> str:
        """Upsert one Place. Same id overwrites (no duplicates)."""
        if place.agent_id != self.agent_id:
            raise ValueError(
                f"place agent_id '{place.agent_id}' does not match store '{self.agent_id}'"
            )
        payload = {
            "id": place.id,
            "agent_id": place.agent_id,
            "pose": {"x": place.pose.x, "y": place.pose.y, "theta": place.pose.theta},
            "timestamp": place.timestamp,
            "confidence": place.confidence,
            "zone": place.payload.zone,
            "sensor": place.payload.sensor,
            "note": place.payload.note,
        }
        self._client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=_qdrant_point_id(place.id),
                    vector=place.vector,
                    payload=payload,
                )
            ],
        )
        return place.id

    def get(self, place_id: str) -> Place | None:
        """Retrieve one Place by id, or None if missing."""
        points = self._client.retrieve(
            collection_name=self.collection,
            ids=[_qdrant_point_id(place_id)],
            with_payload=True,
            with_vectors=True,
        )
        if not points:
            return None
        pt = points[0]
        payload = pt.payload or {}
        pose = payload.get("pose", {})
        vector = list(pt.vector) if pt.vector is not None else []
        return Place(
            id=payload.get("id", place_id),
            agent_id=payload.get("agent_id", self.agent_id),
            vector=vector,
            pose=Pose(
                x=float(pose.get("x", 0.0)),
                y=float(pose.get("y", 0.0)),
                theta=float(pose.get("theta", 0.0)),
            ),
            timestamp=int(payload.get("timestamp", 0)),
            confidence=float(payload.get("confidence", 0.0)),
            payload=Payload(
                zone=str(payload.get("zone", "")),
                sensor=str(payload.get("sensor", "")),
                note=str(payload.get("note", "")),
            ),
        )

    def count(self) -> int:
        """Number of stored places."""
        return self._client.count(collection_name=self.collection).count

    def clear(self) -> None:
        """Remove all places. Keeps collection + indexes intact.

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
        except Exception:
            pass
