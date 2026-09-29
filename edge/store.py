"""Persistent offline local memory (Task 1 storage + Task 2/5 search).

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
    MatchAny,
    PointStruct,
    Range,
    VectorParams,
)

from edge.config import COLLECTION_NAME, DIM, agent_path
from edge.models import (
    HAZARD_KEYWORD,
    Payload,
    Place,
    Pose,
    SwapCandidate,
    place_to_swap_candidate,
    validate_str_list,
    validate_vector,
)

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


def _clean_str_list(values: list[str] | None, name: str) -> list[str]:
    """Check a match-any filter list. None and empty mean no filter."""
    return validate_str_list(values, name) or []


# Task 5 filter fields. Payload indexes are created for these so filtered
# search stays fast in local mode now and on Qdrant Server later.
SEARCH_INDEX_FIELDS: tuple[str, ...] = ("confidence", "timestamp", "zone", "sensor")

# Index type per filter field: numbers get range indexes, labels get
# keyword indexes for exact match filters.
_PAYLOAD_INDEXES: dict[str, str] = {
    "confidence": "float",
    "timestamp": "integer",
    "zone": "keyword",
    "sensor": "keyword",
}


# Page size for full-store scans (pick_swap, clear). Small enough to
# stay light, large enough to keep round trips low.
_SCAN_PAGE: int = 256


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
        self.ensure_payload_indexes()

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

    def ensure_payload_indexes(self) -> None:
        """Create missing payload indexes for the Task 5 filter fields.

        Safe to call on every open: fields that already have an index
        are skipped. A per-field failure only logs a warning so old
        local DB files keep working without indexes.
        """
        try:
            schema = self._client.get_collection(self.collection).payload_schema or {}
        except Exception as exc:
            logger.warning("Could not read payload schema: %s", exc)
            return
        for field in SEARCH_INDEX_FIELDS:
            if field in schema:
                continue
            try:
                self._client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field,
                    field_schema=_PAYLOAD_INDEXES[field],
                )
            except Exception as exc:
                logger.warning(
                    "Could not create payload index for '%s': %s", field, exc
                )

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
        zones: list[str] | None = None,
        sensors: list[str] | None = None,
        since: int | None = None,
        until: int | None = None,
    ) -> list[tuple[Place, float]]:
        """Find nearest places by cosine similarity with optional filters.

        Filters combine with AND: a place must pass every given filter.
        zones and sensors match any value in the list. since and until
        bound the timestamp (unix seconds, both ends included).
        None or an empty list means no filter on that field.

        Returns list of (Place, score) ordered by score descending.
        Corrupt records are skipped. Empty store returns [].
        Raises ValueError for bad vector, top_k, or filter values.
        """
        query = validate_vector(vector)
        if not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive int")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        zones = _clean_str_list(zones, "zones")
        sensors = _clean_str_list(sensors, "sensors")
        for name, bound in (("since", since), ("until", until)):
            if bound is not None and (
                not isinstance(bound, int) or isinstance(bound, bool) or bound < 0
            ):
                raise ValueError(f"{name} must be a unix timestamp >= 0 or None")
        if since is not None and until is not None and since > until:
            raise ValueError("since must not be after until")
        must: list[Any] = []
        if min_confidence > 0.0:
            must.append(
                FieldCondition(key="confidence", range=Range(gte=min_confidence))
            )
        if zones:
            must.append(FieldCondition(key="zone", match=MatchAny(any=zones)))
        if sensors:
            must.append(FieldCondition(key="sensor", match=MatchAny(any=sensors)))
        if since is not None or until is not None:
            time_range: dict[str, Any] = {}
            if since is not None:
                time_range["gte"] = since
            if until is not None:
                time_range["lte"] = until
            must.append(FieldCondition(key="timestamp", range=Range(**time_range)))
        query_filter = Filter(must=must) if must else None
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

    def delete(self, place_id: str) -> bool:
        """Delete one Place by id. Returns True if it existed."""
        points = self._client.retrieve(
            collection_name=self.collection,
            ids=[_qdrant_point_id(place_id)],
            with_payload=False,
            with_vectors=False,
        )
        if not points:
            return False
        self._client.delete(
            collection_name=self.collection,
            points_selector=[_qdrant_point_id(place_id)],
        )
        return True

    def list_places(
        self, limit: int = 50, offset: Any = None
    ) -> tuple[list[Place], Any]:
        """List places in pages. Returns (places, next offset or None).

        Corrupt records are skipped. Used by the dashboard memory view.
        """
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive int")
        points, next_offset = self._client.scroll(
            collection_name=self.collection,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        places = []
        for pt in points:
            place = _place_from_record(pt.payload, pt.vector, self.agent_id)
            if place is not None:
                places.append(place)
        return places, next_offset

    def pick_swap(self, limit: int = 20) -> list[SwapCandidate]:
        """Pick the small set to send on meeting (Task 6, no matching).

        Recent plus high value first: hazard note, then confidence,
        then timestamp. Returns slim SwapCandidate records only.

        Note: exact top-k needs one full scan plus an in-memory sort,
        so this is O(n) memory. Fine for edge stores; revisit only if
        a single robot ever holds tens of thousands of places.
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
            page, offset = self.list_places(limit=_SCAN_PAGE, offset=offset)
            places.extend(page)
            if offset is None:
                break
        places.sort(
            key=lambda p: (
                HAZARD_KEYWORD in p.payload.note.lower(),
                p.confidence,
                p.timestamp,
            ),
            reverse=True,
        )
        return [place_to_swap_candidate(p) for p in places[:limit]]

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
