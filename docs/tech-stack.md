# Tech stack

Locked versions for all 4 people. Use these so branches fit together.

## Backend

- Python 3.11 or 3.12
- FastAPI 0.115 plus uvicorn
- pydantic 2 for data checks
- qdrant-client 1.12 in local mode for edge dev
- numpy for math
- pytest plus httpx for tests
- ruff for lint, mypy for types

## Cloud

- Qdrant Server 1.12 in Docker
- docker compose to run server plus backend

## Dashboard

- Node 20 or higher
- React plus Vite plus TypeScript
- Fetch from backend REST API, no direct DB calls

## Embeddings

- Common interface with one method: image or scan in, vector out
- Default dim 512, set in config, same for all agents
- Test mode uses hash vectors so tests run with no download
- Real mode uses a CLIP style model for images

## Sim

- Python script that makes two drifted paths with shared places
- Saves vectors plus poses to JSON for replay
