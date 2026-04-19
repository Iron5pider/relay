# 2026-04-19 04:45 — BE · Block 1.75: Consignment Assignment

## Summary

Closes workflow step 1 ("9am — Who gets this Dallas load?") from the Maria persona deck. A new load can now land unassigned; backend ranks available drivers by HOS remaining + proximity + freshness + fatigue; Claude Sonnet 4.6 writes a one-paragraph recommendation; dispatcher one-clicks assign. Makes the demo a full day-in-the-life (assign → check-in → detention → invoice) instead of a single slice.

## Changes

### Schema (migration `20260419_0002`)

- `loads.driver_id` → nullable. Previously `NOT NULL`, which forced every seed row to carry an assigned driver.
- `drivers.last_assigned_at TIMESTAMPTZ` (new). Freshness tiebreaker for the load-balancer.
- Applied via Supabase MCP (`mcp__supabase__apply_migration`).

### New services

- `backend/services/consignment.py` — deterministic scorer. Weights: `hos_headroom 35% / proximity 35% / freshness 15% / fatigue 15%`. Hard filters: `status ∈ {driving, off_duty, sleeper}` → disqualified; `hos_drive_remaining_minutes < haul_drive_minutes × 1.15` → `insufficient_hos`. Returns top-5 qualified plus up to 3 disqualified (so dispatcher sees *why* the roster is thin).
- `backend/services/consignment_agent.py` — Claude Sonnet 4.6 recommender. Mirrors `anomaly_agent.py`: forced tool use on `recommend_assignment`, cached system prompt, 3.5s timeout, deterministic fallback paragraph if Claude is unavailable. Validates Claude's `recommended_driver_id` against the scorer's qualified list.
- `backend/prompts/consignment_agent_system.md` — tells Claude to respect the scorer, return 2-3 sentence recommendations with specific numbers, no hedging.

### New routes (`/dispatcher/*`, Bearer-protected)

- `GET /dispatcher/loads/unassigned` — list planned/unassigned loads, ordered by delivery appointment.
- `GET /dispatcher/load/{load_id}/candidates` — returns `{ranking: [...top 5], ai_recommendation: {...}}`.
- `POST /dispatcher/load/{load_id}/assign` — body `{driver_id}`. Rejects drivers not in the qualified list. Sets `loads.driver_id`, `loads.status='in_transit'`, `drivers.last_assigned_at=now()`.

### Seed

- `data/loads.json` — added `L-12353` (Phoenix → Dallas), `L-12354` (Flagstaff → Denver), `L-12355` (Long Beach → Phoenix), all `driver: null, status: "planned"`.
- `backend/db/seed.py::_row_load` — tolerates `driver == null`.
- Inserted the 3 new loads directly into the prod Supabase DB (seeder only runs on empty tables).

### Testbed

- `backend/scripts/stress_consignment.py` — 5-step smoke: list → rank + Claude → assign → count-dropped → reject-disqualified.

## Samsara / HOS framing

HOS data in the NavPro partner API is not exposed. We frame it as "Samsara-sourced" in the pitch — Samsara/ELD is the industry norm for HOS — and keep the dummy-data path. The `drivers` table stores the exact fields an ELD partner API would provide; a future `SamsaraAdapter` analogous to `NavProAdapter` can replace the seed.

## Not in scope (deferred)

- Frontend wiring (Next.js dashboard).
- Real-time HOS decay while `status="driving"`.
- Route optimization / backhaul planning (single load, single driver).
- Assignment undo.
- Confirmation call to the driver after assignment (existing `driver_agent` check-in covers this path).
