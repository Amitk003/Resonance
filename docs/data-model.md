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
  "pair_id": "m1",
  "query_id": "a1",
  "match_id": "b7",
  "score": 0.87,
  "inliers": 12
}
```

## Align result

```json
{
  "transform": {"dx": 0.5, "dy": -0.2, "dtheta": 0.05},
  "confidence": 0.91,
  "used_pairs": 12,
  "threshold": 0.8
}
```

- `transform` moves map B into map A
- `confidence` blends vector score plus shape fit
- Below threshold means no fuse, only log
