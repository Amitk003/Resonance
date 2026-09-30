# Data model

One shared shape. All branches must use it.

## Place record

```json
{
  "id": "a1b2c3",
  "vector": [0.12, -0.03],
  "pose": {"x": 1.5, "y": 2.0, "theta": 0.4},
  "timestamp": 1727000000,
  "confidence": 0.9,
  "payload": {"zone": "hall", "sensor": "cam", "note": ""}
}
```

Rules:

- `id`: string, unique per agent plus local counter
- `vector`: list of floats, length must equal config dim, default 512
- `pose`: x and y in meters, theta in radians
- `timestamp`: unix seconds
- `confidence`: 0 to 1 from the model
- `payload`: zone label, sensor type, short note

## Match result

```json
{
  "pair_id": "robot-b-3~robot-a-7",
  "query_id": "robot-b-3",
  "match_id": "robot-a-7",
  "score": 0.87,
  "inliers": 0
}
```

- `query_id`: swapped candidate from the other robot
- `match_id`: own place with the closest vector
- `score`: cosine similarity from -1 to 1
- `inliers`: 0 here, Task 10 fills it during the shape check
- `pair_id`: stable key built as query plus match with a tilde

## Swap candidate

Slim meeting unit, no zone or sensor text, so radio messages stay small:

```json
{
  "id": "robot-a-7",
  "agent_id": "robot-a",
  "vector": [0.12, -0.03],
  "pose": {"x": 1.5, "y": 2.0, "theta": 0.4},
  "confidence": 0.9,
  "timestamp": 1727000000
}
```

## Align result

```json
{
  "dx": 0.5,
  "dy": -0.2,
  "dtheta": 0.05,
  "inliers": 12,
  "total": 15
}
```

- Moves map B into map A
- `inliers` over `total` is the shape fit from 0 to 1
- Fuse gate lives in Task 13, not here

## Conflict log

```json
{
  "id": "robot-a-7",
  "winner_id": "robot-a-7",
  "loser_id": "robot-a-7",
  "reason": "higher-confidence"
}
```

- Reasons: same, higher-confidence, more-votes, newer, tie-keep-existing
- The loser stays in per-id version history, capped at 10, so no data is lost

## Fuse decision

```json
{
  "fuse": true,
  "score": 0.91,
  "threshold": 0.8,
  "margin": 0.11,
  "reason": "at-or-above-threshold"
}
```

- Boundary counts as fuse
- Reasons: at-or-above-threshold, below-threshold
- Threshold default 0.8, operators move it live
