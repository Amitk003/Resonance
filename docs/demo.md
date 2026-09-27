# Demo and done checks

How to show the full loop works.

## Setup

- Start Qdrant Server plus backend plus dashboard with compose
- Load sim data for robot A and robot B with shared places and drift

## Demo steps

1. Both robots explore offline. Show memory counts grow.
2. Robots meet. Swap 20 vectors. Show match list with scores.
3. Move threshold low, weak matches pass. Move it high, weak matches drop.
4. Align maps. Show transform plus confidence plus time in seconds.
5. Network back. Sync queue sends hazards first. Show server view.
6. Export aligned map as JSON from dashboard.

## Done checks per task

- Store and search: tests pass with no network, top match correct
- Swap and match: replay finds shared places with recall above 0.8
- Transform: error below 0.3 meters and 5 degrees on sim data
- Sync: queue order correct, conflicts logged, no data loss offline
- Dashboard: all pages load from real API, threshold change updates list live

## Owners

See docs/roadmap.md for the one by one task owners.
