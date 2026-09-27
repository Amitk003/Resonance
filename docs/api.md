# API

Base URL: http://localhost:8000. All JSON.

## Health

GET /health returns status.

## Memory

POST /memory/add saves one place record. Body is the place record. Returns saved id.

POST /memory/search finds near places. Body:

```json
{"vector": [0.1], "top_k": 5, "min_confidence": 0.0}
```

Returns a list of match results.

## Meeting

POST /meet/swap picks the small set to send. Body:

```json
{"agent_id": "robot-a", "limit": 20}
```

Returns a list of place records, recent plus high value first.

POST /meet/align takes pairs from both maps and returns the align result. Body:

```json
{"pairs": [{"ax": 0.0, "ay": 0.0, "bx": 0.5, "by": 0.1}], "threshold": 0.8}
```

Returns transform plus confidence. No fuse when below threshold.

## Sync

GET /sync/queue lists items ranked by value.

POST /sync/push sends top items to the server. Body has server URL and limit. Returns uploaded count plus conflicts.

GET /merges lists past aligns with score and threshold.
