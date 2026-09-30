# Resonance

Robots that explore alone stay blind to each other. Each one builds its own map, drifts on its own, and the team waits minutes for a shared picture that may never come.

Resonance gives the team one map in seconds.

Each robot keeps a small private place memory on the device and works fully offline with no GPS and no network. When two robots meet, they swap a handful of vectors, find shared places, and snap their maps together with a scored transform. Hazards jump the sync queue to the cloud first. A dashboard shows every memory, every merge, and every conflict.

## Why teams pick it

- Shared map in seconds, not minutes of heavy registration
- Works with no network and no GPS
- Small radio messages, never full map dumps
- Private by default, shares only on a real meeting
- Every merge carries a score an operator can trust
- Every sync conflict keeps its history, so no data is ever lost

## How it works

1. Robots explore alone. Each stores place vectors locally.
2. They meet. They swap up to 20 slim candidates, hazards first.
3. Fast search finds matches, a shape check verifies fit, and a rigid transform aligns the maps with a confidence score.
4. The cloud receives hazards first, then merge anchors, then rare places.
5. Operators watch memory, merges, thresholds, and conflicts live.

## Quick start

With Docker:

```bash
docker compose up --build
```

- Backend: http://localhost:8000/docs
- Dashboard: http://localhost:5173
- Qdrant Server: http://localhost:6333/dashboard

Backend only:

```bash
pip install -r requirements.txt -r requirements-dev.txt
uvicorn backend.app:app --port 8000
pytest tests/ -q
```

Dashboard only:

```bash
cd dashboard
npm install
npm run dev
```

## What is inside

- `edge/` - offline memory: store, search with filters, swap pick, match, align, sync ranking, conflicts
- `backend/` - FastAPI over the edge layer: memory, search, update, delete, list, swap
- `dashboard/` - React memory view, query builder search page, pose map, merge-ready panels
- `sim/` - coming next: two robot drift simulation with scores
- `docs/` - architecture, data model, API, sync policy, demo, roadmap, tech stack
- `docker-compose.yml` - Qdrant Server plus backend plus dashboard in one command

## Status

Edge memory, search with filters, swap, match, align, sync ranking, and conflicts all run offline with 85 backend tests and 17 dashboard tests green. Next: meeting and sync endpoints, Qdrant Server link, merge history view, and the full two robot demo.
