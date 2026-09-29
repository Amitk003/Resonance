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

from edge.models import Place, SwapCandidate, validate_str_list, validate_vector
from edge.store import PlaceStore


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

    return app


# Default app for `uvicorn backend.app:app` using ./edge_data/<agent_id>/.
app = create_app()
