"""Person 2 Task 2: write and search API for place vectors.

Thin FastAPI layer over Person 1 PlaceStore (Qdrant local mode).
No matching, alignment, sync, or dashboard logic here.

Endpoints (see docs/api.md):
    GET    /health          -> {"status": "ok"}
    GET    /agents          -> [agent ids]
    POST   /memory/add      -> body Place, returns {"id": place.id}
    POST   /memory/bulk     -> body [Place] (1-200), returns {"ids": [...]}
    POST   /memory/search   -> body SearchRequest, returns [SearchHit]
    GET    /memory/list     -> query agent_id + limit + offset, page + total
    GET    /memory/{id}     -> query agent_id, returns Place or 404
    PUT    /memory/{id}     -> body Place, path id must match, returns {"id"}
    DELETE /memory/{id}     -> query agent_id, returns {"deleted": true} or 404
    POST   /meet/swap       -> body agent_id + limit, returns [SwapCandidate]
    POST   /meet/align      -> body two agents, runs meeting, logs MergeRecord
    GET    /merges          -> query limit, newest first merge history
    GET    /sync/queue      -> query agent_id + limit, ranked upload rows
    GET    /sync/conflicts  -> query place_id, kept loser history
    GET    /fuse/threshold  -> live fuse threshold
    PUT    /fuse/threshold  -> body threshold 0 to 1, persisted to disk
    POST   /sync/push       -> push ranked queue, returns uploaded/unchanged/kept

Run:
    uvicorn backend.app:app --port 8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator

from edge.cloud import CloudSync
from edge.config import EDGE_DATA_ROOT
from edge.fuse import DEFAULT_FUSE_THRESHOLD
from edge.merges import MergeLog, run_meeting
from edge.models import (
    MergeRecord,
    Place,
    SwapCandidate,
    validate_str_list,
    validate_vector,
)
from edge.store import PlaceStore
from edge.sync import select_upload


class SearchRequest(BaseModel):
    """Search one agent's local memory. agent_id selects the isolated DB.

    Filters are optional and combine with AND. zones and sensors match
    any value in the list. since and until bound the timestamp in unix
    seconds, both ends included.
    """

    agent_id: str = Field(min_length=1)
    vector: list[float]
    top_k: int = Field(default=5, ge=1, le=100)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    zones: list[str] | None = Field(default=None)
    sensors: list[str] | None = Field(default=None)
    since: int | None = Field(default=None, ge=0)
    until: int | None = Field(default=None, ge=0)

    @field_validator("vector")
    @classmethod
    def _validate_vector(cls, v: Any) -> list[float]:
        return validate_vector(v)

    @field_validator("zones", "sensors")
    @classmethod
    def _validate_labels(cls, v: Any, info: Any) -> list[str] | None:
        return validate_str_list(v, info.field_name)

    @model_validator(mode="after")
    def _validate_window(self) -> SearchRequest:
        if (
            self.since is not None
            and self.until is not None
            and self.since > self.until
        ):
            raise ValueError("since must not be after until")
        return self


class SearchHit(BaseModel):
    """One search result: matched place plus cosine score."""

    id: str
    score: float
    place: Place


class PlaceList(BaseModel):
    """One page of the dashboard memory view."""

    places: list[Place]
    next_offset: Any = None
    total: int


class MeetSwapRequest(BaseModel):
    """Pick the small set to send on meeting (Task 6)."""

    agent_id: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=100)


class MeetAlignRequest(BaseModel):
    """Run one meeting between two agents and log it (Task 12)."""

    agent_a: str = Field(min_length=1)
    agent_b: str = Field(min_length=1)
    swap_limit: int = Field(default=20, ge=1, le=100)
    top_k: int = Field(default=1, ge=1, le=20)
    min_score: float = Field(default=0.0, ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def _validate_pair(self) -> MeetAlignRequest:
        if self.agent_a == self.agent_b:
            raise ValueError("agent_a and agent_b must differ")
        return self


class SyncItem(BaseModel):
    """One upload queue row: the place, its score, and why."""

    place: Place
    score: float
    reasons: list[str]


class ThresholdSet(BaseModel):
    """Live fuse threshold, moved by operators (Task 16 uses this)."""

    threshold: float = Field(ge=0.0, le=1.0)


class ConflictEntry(BaseModel):
    """One conflict decision served to the dashboard log."""

    id: str
    winner_id: str
    loser_id: str
    reason: str


class SyncPushRequest(BaseModel):
    """Push ranked places to the shared server (Task 15)."""

    agent_id: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=100)
    server_url: str | None = Field(default=None)


class SyncPushResponse(BaseModel):
    """Outcome counts plus every conflict decision of one push."""

    uploaded: int
    unchanged: int
    kept: int = 0
    conflicts: list[ConflictEntry]


def create_app(storage_root: Path | str | None = None) -> FastAPI:
    """Build the FastAPI app. storage_root isolates tests via tmp_path."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        for store in app.state.stores.values():
            store.close()
        app.state.stores.clear()
        app.state.clouds.clear()

    app = FastAPI(title="Resonance Edge API", lifespan=lifespan)
    # Demo accepts browser calls from any origin (dashboard may run on
    # :5173 locally or :80 in compose). Restrict via CORS_ORIGINS in prod.
    origins = os.environ.get("CORS_ORIGINS", "*")
    allow = ["*"] if origins.strip() == "*" else [o.strip() for o in origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.storage_root = storage_root
    stores: dict[str, PlaceStore] = {}
    app.state.stores = stores
    app.state.clouds: dict[str, CloudSync] = {}
    app.state.merge_log = MergeLog(
        Path(storage_root) / "merges.json" if storage_root is not None else None
    )
    app.state.threshold_path = (
        Path(storage_root) / "threshold.txt" if storage_root is not None else None
    )
    app.state.fuse_threshold = DEFAULT_FUSE_THRESHOLD
    if app.state.threshold_path is not None and app.state.threshold_path.exists():
        try:
            app.state.fuse_threshold = float(
                app.state.threshold_path.read_text(encoding="utf-8").strip()
            )
        except (OSError, ValueError):
            pass
    elif (Path("edge_data") / "threshold.txt").exists() and storage_root is None:
        try:
            app.state.fuse_threshold = float(
                (Path("edge_data") / "threshold.txt").read_text(encoding="utf-8").strip()
            )
        except (OSError, ValueError):
            pass

    def agent_anchors(agent_id: str) -> frozenset[str]:
        """Place ids that helped align this agent's maps so far."""
        found: set[str] = set()
        for record in app.state.merge_log.list(limit=200):
            if record.agent_a == agent_id or record.agent_b == agent_id:
                found.update(record.anchor_ids)
        return frozenset(found)

    def get_store(agent_id: str) -> PlaceStore:
        if not agent_id or not agent_id.strip():
            raise HTTPException(status_code=422, detail="agent_id must be non-empty")
        store = app.state.stores.get(agent_id)
        if store is None:
            try:
                store = PlaceStore(agent_id=agent_id, storage_root=storage_root)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            app.state.stores[agent_id] = store
        return store

    def get_cloud(url: str) -> CloudSync:
        cloud = app.state.clouds.get(url)
        if cloud is None:
            cloud = CloudSync(url=url, timeout=3)
            app.state.clouds[url] = cloud
        return cloud

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/agents", response_model=list[str])
    def list_agents() -> list[str]:
        known = set(app.state.stores.keys())
        root = Path(storage_root) if storage_root is not None else EDGE_DATA_ROOT
        if root.exists():
            for child in root.iterdir():
                if child.is_dir():
                    known.add(child.name)
        return sorted(known)

    @app.post("/memory/add")
    def memory_add(place: Place) -> dict[str, str]:
        store = get_store(place.agent_id)
        try:
            pid = store.add(place)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"id": pid}

    @app.post("/memory/bulk")
    def memory_bulk(places: list[Place]) -> dict[str, list[str]]:
        if not isinstance(places, list) or not 1 <= len(places) <= 200:
            raise HTTPException(
                status_code=422, detail="body must hold 1 to 200 places"
            )
        by_agent: dict[str, list[Place]] = {}
        for place in places:
            by_agent.setdefault(place.agent_id, []).append(place)
        ids: list[str] = []
        for agent_id, group in by_agent.items():
            store = get_store(agent_id)
            try:
                ids.extend(store.add_many(group))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ids": ids}

    @app.post("/memory/search", response_model=list[SearchHit])
    def memory_search(req: SearchRequest) -> list[SearchHit]:
        store = get_store(req.agent_id)
        try:
            hits = store.search(
                vector=req.vector,
                top_k=req.top_k,
                min_confidence=req.min_confidence,
                zones=req.zones,
                sensors=req.sensors,
                since=req.since,
                until=req.until,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return [
            SearchHit(id=place.id, score=score, place=place) for place, score in hits
        ]

    @app.get("/memory/list", response_model=PlaceList)
    def memory_list(
        agent_id: str = Query(..., description="Agent id, e.g. robot-a"),
        limit: int = Query(default=50, ge=1, le=200),
        offset: Any | None = None,
    ) -> PlaceList:
        store = get_store(agent_id)
        try:
            places, next_offset = store.list_places(limit=limit, offset=offset)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return PlaceList(
            places=places, next_offset=next_offset, total=store.count()
        )

    @app.get("/memory/{place_id}", response_model=Place)
    def memory_get(
        place_id: str,
        agent_id: str = Query(..., description="Agent id, e.g. robot-a"),
    ) -> Place:
        store = get_store(agent_id)
        saved = store.get(place_id)
        if saved is None:
            raise HTTPException(status_code=404, detail="place not found")
        return saved

    @app.put("/memory/{place_id}")
    def memory_update(place_id: str, place: Place) -> dict[str, str]:
        if place.id != place_id:
            raise HTTPException(
                status_code=422, detail="path id must match body id"
            )
        store = get_store(place.agent_id)
        try:
            store.add(place)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"id": place.id}

    @app.delete("/memory/{place_id}")
    def memory_delete(
        place_id: str,
        agent_id: str = Query(..., description="Agent id, e.g. robot-a"),
    ) -> dict[str, bool]:
        store = get_store(agent_id)
        if not store.delete(place_id):
            raise HTTPException(status_code=404, detail="place not found")
        return {"deleted": True}

    @app.post("/meet/swap", response_model=list[SwapCandidate])
    def meet_swap(req: MeetSwapRequest) -> list[SwapCandidate]:
        store = get_store(req.agent_id)
        try:
            return store.pick_swap(limit=req.limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/meet/align", response_model=MergeRecord)
    def meet_align(req: MeetAlignRequest) -> MergeRecord:
        store_a = get_store(req.agent_a)
        store_b = get_store(req.agent_b)
        try:
            record = run_meeting(
                store_a,
                store_b,
                swap_limit=req.swap_limit,
                top_k=req.top_k,
                min_score=req.min_score,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if record is None:
            raise HTTPException(
                status_code=400, detail="no consensus between the two maps"
            )
        app.state.merge_log.append(record)
        return record

    @app.get("/merges", response_model=list[MergeRecord])
    def merge_history(limit: int = Query(default=50, ge=1, le=200)) -> list[MergeRecord]:
        try:
            return app.state.merge_log.list(limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/sync/queue", response_model=list[SyncItem])
    def sync_queue(
        agent_id: str = Query(..., description="Agent id, e.g. robot-a"),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[SyncItem]:
        store = get_store(agent_id)
        try:
            ranked = select_upload(
                store, limit=limit, anchors=agent_anchors(agent_id)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return [
            SyncItem(place=place, score=score, reasons=reasons)
            for place, score, reasons in ranked
        ]

    @app.get("/fuse/threshold")
    def get_threshold() -> dict[str, float]:
        return {"threshold": app.state.fuse_threshold}

    @app.put("/fuse/threshold")
    def set_threshold(body: ThresholdSet) -> dict[str, float]:
        app.state.fuse_threshold = body.threshold
        path = app.state.threshold_path
        if path is None:
            path = Path("edge_data") / "threshold.txt"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(body.threshold), encoding="utf-8")
        except OSError:
            pass
        return {"threshold": app.state.fuse_threshold}

    @app.get("/sync/conflicts", response_model=list[ConflictEntry])
    def sync_conflicts(
        place_id: str = Query(..., description="Place id, e.g. robot-a-1"),
    ) -> list[ConflictEntry]:
        out: list[ConflictEntry] = []
        for cloud in app.state.clouds.values():
            for place in cloud.conflict_history(place_id):
                out.append(
                    ConflictEntry(
                        id=place_id,
                        winner_id=place_id,
                        loser_id=place.id,
                        reason="history",
                    )
                )
        return out

    @app.post("/sync/push", response_model=SyncPushResponse)
    def sync_push(req: SyncPushRequest) -> SyncPushResponse:
        store = get_store(req.agent_id)
        try:
            ranked = select_upload(
                store, limit=req.limit, anchors=agent_anchors(req.agent_id)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        url = req.server_url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        try:
            cloud = get_cloud(url)
            report = cloud.push_many([place for place, _, _ in ranked])
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=f"cloud unreachable at {url}: {exc}"
            ) from exc
        return SyncPushResponse(
            uploaded=report.uploaded,
            unchanged=report.unchanged,
            kept=report.kept,
            conflicts=[ConflictEntry(**vars(log)) for log in report.conflicts],
        )

    return app


# Default app for `uvicorn backend.app:app` using ./edge_data/<agent_id>/.
app = create_app()
