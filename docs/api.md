# API

Base URL: http://localhost:8000. All JSON.

## Health

GET /health returns status.

GET /agents lists known agent ids from open stores and disk.

## Memory

POST /memory/add saves one place record. Body is the place record. Returns saved id.

POST /memory/search finds near places. Body:

```json
{"agent_id": "robot-a", "vector": [0.1], "top_k": 5, "min_confidence": 0.0}
```

Optional filters combine with AND: `zones` and `sensors` match any
value in the list, `since` and `until` bound the timestamp in unix
seconds, both ends included. Omit a filter or pass an empty list to
skip it.

Returns a list of match results with id, score, and place.

## Read one place

GET /memory/{id}?agent_id=robot-a returns the place or 404.

## Update

PUT /memory/{id} saves the full place record. Path id must match body id or the call fails with 422. Same id overwrites. Returns saved id.

## Delete

DELETE /memory/{id}?agent_id=robot-a removes one place. Returns deleted true or 404 when missing.

## List

GET /memory/list?agent_id=robot-a&limit=50&offset=0 returns one page plus total count and next offset. The dashboard memory view uses this.

## Meeting

POST /meet/swap picks the small set to send. Body:

```json
{"agent_id": "robot-a", "limit": 20}
```

Returns slim swap candidates, hazards first.

POST /meet/align runs one meeting between two agents and logs it. Body:

```json
{"agent_a": "robot-a", "agent_b": "robot-b"}
```

Returns the scored merge record with transform and inlier anchor ids, or 400 when the maps share too few places for a consensus.

GET /merges?limit=50 lists past merge records, newest first.

## Fuse threshold

GET /fuse/threshold returns the live threshold. PUT /fuse/threshold saves it and persists to disk so restarts keep it.

## Sync queue

GET /sync/queue?agent_id=robot-a&limit=20 returns ranked upload rows
with place, score, and reasons. Anchors come from inlier matches in
the merge history of that agent, so aligned places rise on their own.

## Push to cloud

POST /sync/push sends the ranked queue to the shared server. Body:

```json
{"agent_id": "robot-a", "limit": 20}
```

Optional `server_url` overrides the QDRANT_URL env value, default
http://localhost:6333. Returns uploaded, unchanged, and kept counts
plus every conflict decision. Kept means the server copy won and no
write happened. Unreachable server answers 503.

GET /sync/conflicts?place_id=robot-a-1 lists kept loser history for one id.
