# Resonance — Change Log

> Rule: every change (human or coding agent) must add a row below with
> UTC date-time, author/agent, files touched, what changed and why.
> This supplements `git log` so Person 1-4 can see who changed what and when.
> Format: newest entries on top.

| Date (UTC) | Author / Agent | Files | What changed + why |
|---|---|---|---|
| 2026-09-29 | Prince (Person 2) + Muse Spark (coding agent) | `edge/store.py`, `backend/__init__.py`, `backend/app.py`, `tests/test_api.py`, `requirements.txt`, `requirements-dev.txt` | Task 2: write and search API. Added `PlaceStore.search(vector, top_k, min_confidence)` (cosine via Qdrant local mode, confidence Range filter, corrupt records skipped) with shared `_place_from_record` helper for get/search. New FastAPI app `backend/app.py` with `GET /health`, `POST /memory/add` (Place body, per-agent store, returns id), `POST /memory/search` (agent_id selects isolated DB, returns id/score/place hits). `create_app(storage_root)` factory keeps tests isolated via tmp_path. 10 new API tests offline (health, add, top-match-correct, empty, top_k, min_confidence, per-agent isolation, 422s, upsert). Added fastapi/uvicorn to runtime deps, httpx to dev deps per tech-stack. |
| 2026-09-29 | Amit (review fixes) | `edge/store.py`, `edge/models.py`, `edge/config.py`, `edge/__init__.py`, `tests/test_store.py`, `requirements.txt`, `requirements-dev.txt` | Review fixes: removed em dashes, dropped id-prefix rule (store agent check is the single guard), moved payload indexes and threshold out to the tasks that need them, added add_many bulk write, strict get returns None on corrupt payload, close logs instead of swallowing errors, project UUID namespace, public collection_info, pinned deps with dev split. |
| 2026-09-29 | Nirmit (Person 1) + Muse Spark (coding agent) | `edge/__init__.py`, `edge/config.py`, `edge/models.py`, `edge/store.py`, `tests/__init__.py`, `tests/test_store.py`, `requirements.txt` | Task 1: offline local place store with Qdrant 1.12 local mode. Per-agent dirs `./edge_data/<agent_id>/`, collection `places` 512-d COSINE. Pydantic Place contract (id `agent-counter`, vector 512, confidence 0-1). Upsert semantics, get/count/clear/close, payload indexes for Task 5. 11 pytest tests offline (config, add/get, count, clear, persistence, missing-id, upsert, invalid vector/confidence, isolation, zero-vector). No search/matching/sync/API. |
| 2026-09-29 | Nirmit (Person 1) + Muse Spark (coding agent) | `edge/store.py`, `tests/test_store.py` | Fix: `clear()` via scroll+delete-by-id (delete_collection+recreate unreliable in qdrant-client 1.12 local mode). Fix: tests compare cosine direction not raw magnitude (Qdrant COSINE L2-normalizes on retrieval). Fix: invalid-vector test uses `Place(...)` constructor (Pydantic `model_copy` skips validation). |

## Task 1 — Final API (for Person 2 `/memory/add`)

```python
from edge.models import Place
from edge.store import PlaceStore

store = PlaceStore(agent_id="robot-a")  # isolated ./edge_data/robot-a/
place_id: str = store.add(place)        # upsert, returns place.id
saved: Place | None = store.get(place_id)
total: int = store.count()
store.clear()
store.close()
```

## Assumptions / compatibility notes

1. Qdrant point id = deterministic UUID5 of Place `id` (Qdrant rejects raw `robot-a-42`). Original id kept in payload.
2. `get()` returns L2-normalized vector (Qdrant COSINE behavior). Direction preserved, magnitude not. Fine for similarity; document for Task 9.
3. Payload indexes (`agent_id, timestamp, confidence, zone, sensor`) created now for Task 5; no filtering logic in Task 1. Local Qdrant warns indexes have no effect locally — harmless, needed for future server mode.
4. IDs caller-supplied as `<agent_id>-<counter>`; cross-agent `add()` rejected with `ValueError`.
5. `storage_root` param allows tests to use `tmp_path` instead of real `./edge_data/`.
6. Pinned `qdrant-client==1.12.*` per locked tech stack (env had 1.18.0, downgraded to 1.12.2).

## Design

```text
config.py (DIM=512, THRESHOLD=0.8, EDGE_DATA_ROOT)
    |
    v
models.py -> Place(id, agent_id, vector[512], pose, timestamp, confidence, payload)
    |
    v
store.py -> PlaceStore(agent_id)
    |---> ./edge_data/robot-a/ (Qdrant Local, places, COSINE)
    |---> ./edge_data/robot-b/ (Qdrant Local, places, COSINE)
    |
    v
Future Tasks: Search / Matching (build on this store, do not modify contract)
```

## Template for next change (copy row)

| YYYY-MM-DD HH:MM UTC | Name (Person N) + agent (if any) | files | what + why |
