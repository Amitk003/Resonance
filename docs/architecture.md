# Architecture

Simple view of the full system.

## Parts

1. Edge Agent on each robot
   - Takes images or scans
   - Turns each place into a vector
   - Stores it locally with Qdrant Edge
   - Searches locally with no network

2. Meeting layer for two robots
   - Finds that robots are close
   - Swaps a small set of vectors
   - Finds matches with fast search
   - Checks shape fit and returns a transform plus a score

3. Cloud and dashboard at base
   - Qdrant Server holds the shared view
   - Sync sends only high value items
   - Dashboard shows memory, merges, threshold, sync, export

## Flows

Write offline: sensor to vector to local store. Always works.

Meet and align: meet to swap to search to shape check to transform to fuse.

Sync online: rank local points by value to upload in order to fix conflicts to show result.

## Rules

- Private by default. Share only on meeting.
- Small messages. Never send full memory.
- Score every merge. Operator can move the threshold.
