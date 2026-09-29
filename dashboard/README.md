# Resonance Memory Dashboard (Person 4, Tasks 4 and 8)

Memory view page and Search results page for the local place memory
of each edge robot. Reads and writes through the backend REST API.
No direct DB calls.

## Run

Terminal 1, backend (repo root):

```
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --port 8000
```

Terminal 2, dashboard:

```
cd dashboard
npm install
npm run dev
```

Open http://localhost:5173 in a browser.

## What the page does

- Header: backend address box with Connect, online status with Retry,
  agent switch between robot-a and robot-b.
- Stat cards: places in view, total stored, average confidence,
  zone count, sensor count. All update live.
- Memory list: text filter, zone filter, sort, page size, Refresh,
  Clear filters. Click a row to select it.
- Pose map: SVG plot of x and y with heading ticks. Click a dot
  to select that place.
- Details: full record with raw JSON, Edit (zone, sensor, note,
  confidence) through PUT, Delete with confirm through DELETE.
- Similar search: pick a source place, move Top K and min confidence
  sliders, add zone, sensor, and time filters, Find similar through
  POST /memory/search. Click a match to jump to it.
- Add place: form with input checks, vector is fresh random or near
  the selected place. Seed demo adds 18 clustered places so similar
  search shows clear high and low scores.

Every button calls the API or updates the view. No dead buttons.

## What the Search results page does

- Header tabs switch between Memory and Search. Both pages share
  the backend address, online status, and agent switch.
- Query builder with three sources: a stored place vector, a noisy
  copy near a place, or a fresh random vector. Top K and min
  confidence sliders.
- Zone and sensor checkbox groups plus Since and Until date pickers,
  all sent to POST /memory/search. Reset filters clears them.
- Ranked results table with score bars, zone badges, sensor,
  confidence, and time. Click a match to inspect it.
- Result map plots match poses with clickable dots. Match details
  panel supports the same working edit and delete as Memory.
- Past searches are saved in the browser with source, filters,
  counts, and top score. Entries re-run the exact query, delete
  singly, or clear all.

## Tech

Vite plus React plus TypeScript. Plain CSS in `src/styles.css`.
Typed client in `src/api.ts` matches `docs/api.md`.
Pages live in `src/pages/`, shared bits in `src/common.ts`.
History helpers in `src/searchHistory.ts` with vitest cover.

## Known limits

- Memory list shows one page (max 200 rows). The API returns
  `next_offset`, but paging controls are not built yet.
- Agent switch covers robot-a and robot-b only. A backend
  agent-list endpoint is needed before this can be dynamic.
- Seed demo sends one POST per place. Fine for 18 demo rows.
  Bulk import needs a backend bulk endpoint first.
