"""Person 2 Task 2: write and search API for place vectors.

Thin FastAPI layer over Person 1 PlaceStore (Qdrant local mode).
No matching, alignment, sync, or dashboard logic here.

Endpoints (see docs/api.md):
    GET    /health          -> {"status": "ok"}
    POST   /memory/add      -> body Place, returns {"id": place.id}
    POST   /memory/search   -> body SearchRequest, returns [SearchHit]
    GET    /memory/list     -> query agent_id + limit, returns page + total
    GET    /memory/{id}     -> query agent_id, returns Place or 404
    PUT    /memory/{id}     -> body Place, path id must match, returns {"id"}
    DELETE /memory/{id}     -> query agent_id, returns {"deleted": true} or 404
    POST   /meet/swap       -> body agent_id + limit, returns [SwapCandidate]
    POST   /meet/align      -> body two agents, runs meeting, logs MergeRecord
    GET    /merges          -> query limit, newest first merge history
    GET    /sync/queue      -> query agent_id + limit, ranked upload rows
    GET    /fuse/threshold  -> live fuse threshold
    PUT    /fuse/threshold  -> body threshold 0 to 1, moved by operators

Run:
    uvicorn backend.app:app --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator

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


def create_app(storage_root: Path | str | None = None) -> FastAPI:
    """Build the FastAPI app. storage_root isolates tests via tmp_path."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        for store in app.state.stores.values():
            store.close()
        app.state.stores.clear()

    app = FastAPI(title="Resonance Edge API", lifespan=lifespan)
    # Dashboard runs on :5173 and calls this API, so allow browser access.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.storage_root = storage_root
    stores: dict[str, PlaceStore] = {}
    app.state.stores = stores
    app.state.merge_log = MergeLog(
        Path(storage_root) / "merges.json" if storage_root is not None else None
    )
    app.state.fuse_threshold = DEFAULT_FUSE_THRESHOLD

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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/memory/add")
    def memory_add(place: Place) -> dict[str, str]:
        store = get_store(place.agent_id)
        try:
            pid = store.add(place)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"id": pid}

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
        agent_id: str,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> PlaceList:
        store = get_store(agent_id)
        try:
            places, next_offset = store.list_places(limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return PlaceList(
            places=places, next_offset=next_offset, total=store.count()
        )

    @app.get("/memory/{place_id}", response_model=Place)
    def memory_get(place_id: str, agent_id: str) -> Place:
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
    def memory_delete(place_id: str, agent_id: str) -> dict[str, bool]:
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
        agent_id: str, limit: int = Query(default=20, ge=1, le=100)
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
        return {"threshold": app.state.fuse_threshold}

    return app


# Default app for `uvicorn backend.app:app` using ./edge_data/<agent_id>/.
app = create_app()
