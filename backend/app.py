"""Person 2 Task 2: write and search API for place vectors.

Thin FastAPI layer over Person 1 PlaceStore (Qdrant local mode).
No matching, alignment, sync, or dashboard logic here.

Endpoints (see docs/api.md):
    GET  /health          -> {"status": "ok"}
    POST /memory/add      -> body Place, returns {"id": place.id}
    POST /memory/search   -> body SearchRequest, returns [SearchHit]

Run:
    uvicorn backend.app:app --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from edge.config import DIM
from edge.models import Place
from edge.store import PlaceStore


class SearchRequest(BaseModel):
    """Search one agent's local memory. agent_id selects the isolated DB."""

    agent_id: str = Field(min_length=1)
    vector: list[float]
    top_k: int = Field(default=5, ge=1, le=100)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("vector")
    @classmethod
    def _validate_vector(cls, v: Any) -> list[float]:
        if not isinstance(v, list):
            raise ValueError("vector must be a list of floats")
        if len(v) != DIM:
            raise ValueError(f"vector must have exactly {DIM} values")
        for item in v:
            if not isinstance(item, (int, float)):
                raise ValueError("vector values must be numeric")
        return [float(x) for x in v]


class SearchHit(BaseModel):
    """One search result: matched place plus cosine score."""

    id: str
    score: float
    place: Place


def create_app(storage_root: Path | str | None = None) -> FastAPI:
    """Build the FastAPI app. storage_root isolates tests via tmp_path."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        for store in app.state.stores.values():
            store.close()
        app.state.stores.clear()

    app = FastAPI(title="Resonance Edge API (Person 2 Task 2)", lifespan=lifespan)
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
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return [
            SearchHit(id=place.id, score=score, place=place) for place, score in hits
        ]

    return app


# Default app for `uvicorn backend.app:app` using ./edge_data/<agent_id>/.
app = create_app()
