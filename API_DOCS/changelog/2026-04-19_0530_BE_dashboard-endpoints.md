# 2026-04-19 05:30 — BE · Dashboard read endpoints + POD/send mutations

## Summary

Frontend-facing read surface for the four main dashboard sections in the Maria persona deck: **fleet live feed**, **detention live view**, **billing**, **POD**. Every endpoint returns the `{ok, data, error}` envelope and is Bearer-protected — no new auth story, same dep as the rest of `/dispatcher/*`. Dashboard can now render the whole day-in-the-life screen without querying the DB directly.

## Schema (migration `20260419_0003`)

- `loads.pod_url / pod_signed_by / pod_received_at` — proof-of-delivery fields.
- `invoices.sent_at / sent_to_email` — invoice send audit trail.
- Applied via Supabase MCP.

## New routes (all `/dispatcher/*`, Bearer-protected)

### Section 1 — Fleet live feed
- `GET /dispatcher/fleet/live` — every driver with GPS + HOS + fatigue + active-load summary, plus `adapter` (`navpro` vs `mock`) so the map can label the data source.
- `GET /dispatcher/driver/{id}` — full driver detail + active load + last 5 calls.
- `GET /dispatcher/driver/{id}/timeline` — chronological feed of check-in calls, voice calls, and load assignments. One query the dashboard can drop straight into a vertical timeline component.

### Section 2 — Detention live view
- `GET /dispatcher/detentions/active` — every load in detention (status `exception` OR `elapsed > free`). Each row: live detention clock (`minutes_past_free`, `projected_amount` computed from the rate), latest detention call (if any), `call_fired` boolean, linked invoice id/status/amount. Sorted by `minutes_past_free DESC` so the worst offender is row 1.
- `GET /dispatcher/detention/{load_id}` — full detail: load + driver + clock + all detention calls chronologically + all `detention_events` (AP contact, commitment, refusal, escalation step) + invoice snapshot.

### Section 3 — Billing
- `GET /dispatcher/invoices?status=` — list + totals aggregated by status (for the summary strip at the top of the billing page).
- `GET /dispatcher/invoices/{id}` — full detail: invoice + load + driver + triggering call.
- `POST /dispatcher/invoices/{id}/send` — state transition. Stamps `sent_at`, `sent_to_email`, flips status to `sent`. Does NOT actually dispatch email — that's an integration concern (SendGrid / Postmark) for a later phase; the audit trail + status flip is what the UI needs now. Returns 409 `already_sent` on re-post.

### Section 4 — POD
- `POST /dispatcher/load/{id}/pod` — body `{pod_url, signed_by}`. Stamps `pod_received_at = now()`, flips load status to `delivered`. Frontend uploads the signed BOL image to its own Supabase Storage / S3 and hands us the URL. 409 `pod_already_recorded` on re-post.

## Helpers introduced

`routes/dashboard.py` ships small private helpers that compose the nested shapes the FE will consume repeatedly:

- `_driver_lite`, `_broker_lite` — tiny object shapes for foreign references.
- `_driver_snapshot` — full driver row with HOS + fatigue + GPS + next-check-in timestamps.
- `_load_snapshot` — flat load row + nested pickup/delivery + embedded POD block.
- `_call_summary` — the canonical voice-call shape the FE will render in timelines and detail panes.
- `_detention_clock` — shared math: `minutes_past_free`, `projected_amount`. Same formula the ElevenLabs agent tool `compute_detention_charge` uses; intentionally not wrapping that tool to avoid cycling dependencies.

## Not-in-scope (deferred)

- Real email dispatch on `/invoices/{id}/send`.
- POD file upload — frontend handles storage; we only persist the URL.
- SSE / WebSocket streams for live feed ticks. Polling every 15s on `/fleet/live` + `/detentions/active` is enough for the demo.
- Driver status *history* beyond what voice-call purposes encode. A proper `driver_status_log` table is a future phase.
- Pagination / cursors. Hackathon scope — single demo dispatcher, <50 rows per list.

## Testbed

- `backend/scripts/stress_dashboard.py` — 4-section smoke covering all new endpoints + POD + send mutations. Idempotent re-runs (POD/send return 409 on second call; treated as success so the smoke doesn't flake).
