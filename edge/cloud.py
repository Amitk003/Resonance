"""Link to Qdrant Server (Task 15, push only).

CloudSync pushes ranked local places into one shared server
collection. Same place id on both sides triggers the Task 11
conflict rules, identical resends are skipped, losers stay in a
per-id version history. Pull and live serving stay out of scope.

The module talks plain QdrantClient calls, so it runs unchanged
against a remote URL, a local path, or :memory:. Tests use
:memory:, which exercises the exact same code path as remote.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from edge.config import COLLECTION_NAME, DIM
from edge.models import Place
from edge.store import place_from_record, place_payload, point_id_for
from edge.sync import ConflictLog, resolve_conflict, vectors_same


@dataclass
class PushReport:
    """Outcome of one push: counts plus every conflict decision."""

    uploaded: int = 0
    unchanged: int = 0
    kept: int = 0
    conflicts: list[ConflictLog] = field(default_factory=list)


def _server_payload(place: Place) -> dict:
    """Same payload shape the edge store uses, so both sides match."""
    return place_payload(place)


def _looks_same(a: Place, b: Place) -> bool:
    """Same content across the edge/server boundary.

    Metadata must match exactly. Vectors compare by direction with a
    float32 tolerant threshold because the server L2-normalizes.
    """
    if not (
        a.confidence == b.confidence
        and a.timestamp == b.timestamp
        and a.pose == b.pose
        and a.payload == b.payload
    ):
        return False
    return vectors_same(list(a.vector), list(b.vector))


class CloudSync:
    """Push side of the edge to cloud link."""

    def __init__(
        self,
        client: QdrantClient | None = None,
        url: str | None = None,
        collection: str = COLLECTION_NAME,
        timeout: int = 5,
    ) -> None:
        if client is None and url is None:
            raise ValueError("pass a client or a server url")
        if client is not None:
            self._client = client
        else:
            self._client = QdrantClient(url=url, timeout=timeout)
        self.collection = collection
        self.history: dict[str, list[Place]] = {}
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self._client.collection_exists(self.collection):
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
            )

    def _read_server(self, place_id: str) -> Place | None:
        points = self._client.retrieve(
            collection_name=self.collection,
            ids=[point_id_for(place_id)],
            with_payload=True,
            with_vectors=True,
        )
        if not points:
            return None
        return place_from_record(points[0].payload, points[0].vector, "")

    def _write_server(self, place: Place) -> None:
        self._client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=point_id_for(place.id),
                    vector=place.vector,
                    payload=_server_payload(place),
                )
            ],
        )

    def push_place(self, place: Place) -> tuple[str, ConflictLog | None]:
        """Push one place. Returns outcome plus the conflict log, if any.

        Outcomes: uploaded (new or incoming winner written), unchanged
        (same content already on server), kept (server winner kept, no
        write). Losers are never dropped, they land in history.
        """
        existing = self._read_server(place.id)
        if existing is None:
            self._write_server(place)
            return "uploaded", None
        if _looks_same(existing, place):
            log = ConflictLog(place.id, place.id, place.id, "same")
            return "unchanged", log
        winner, log = resolve_conflict(existing, place, history=self.history)
        if vectors_same(list(winner.vector), list(place.vector)) and (
            winner.confidence == place.confidence
            and winner.timestamp == place.timestamp
        ):
            self._write_server(winner)
            return "uploaded", log
        return "kept", log

    def push_many(self, places: list[Place]) -> PushReport:
        """Push many places in rank order. Returns the full report."""
        report = PushReport()
        for place in places:
            outcome, log = self.push_place(place)
            if outcome == "unchanged":
                report.unchanged += 1
            elif outcome == "kept":
                report.kept += 1
            else:
                report.uploaded += 1
            if log is not None and log.reason != "same":
                report.conflicts.append(log)
        return report

    def conflict_history(self, place_id: str) -> list[Place]:
        """Loser versions kept for one id, oldest first."""
        return list(self.history.get(place_id, []))
