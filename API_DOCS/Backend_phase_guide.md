# Relay Backend — Phased Implementation Guide

> **Structure mirrors the Notion Build Plan (Sequential).** Build Plan defines the hackathon cadence — blocks, gates, dev-pair splits, ruthless cuts, pivot signals. This doc is the **backend-specific checklist per block**: Pydantic / FastAPI / Twilio / ElevenLabs / Postgres / Pusher mechanics that Build Plan leaves implicit.
>
> **Precedence:** `CLAUDE.md` = contract · API Models (Notion) = canonical spec · **Build Scope (Notion) = P0 prioritization lock** · Build Plan (Notion) = canonical sequence · this doc = backend execution detail. On any conflict, the Notion pages win — and when Build Scope and Build Plan disagree, **Build Scope wins** (it is newer and scopes P0 more tightly).

> **Scope reconciliation (2026-04-19).** The Notion **Build Scope** page narrows P0 to **three features** and moves two Build Plan workflows to "Later — Good-to-haves":
> - **P0 ships:** Feature 1 — Dispatch Check-In (F6b proactive driver check-in) · Feature 2 — Anomaly Detection + Auto-Call (extends F6b, adds `missed_checkin` trigger) · Feature 3 — Auto-Invoice via Escalation Call (F2 + F4 detention hero).
> - **Deferred:** F5 Broker Check-Call Batch · F6 Inbound Multilingual Driver IVR. Prompts, agent, inbound Twilio webhook branch, and `record_driver_checkin` tool stay documented but **do not ship in the demo**.
> - **Schema impact:** add `missed_checkin` to `CheckinTriggerReason` enum in API Models §2, `backend/models/schemas.py`, and `frontend/shared/types.ts` — same PR. No other schema changes.
> - **Demo arc:** two beats (not four). Beat 1 = driver check-in / anomaly (Feature 1 + 2). Beat 2 = receiver escalation → invoice (Feature 3).
> Blocks in this doc marked **[DEFERRED]** below are the workflows moved out of P0. Keep the scaffolding comments for a post-hackathon resume.

## How to use this doc

- **Gate-based, not time-based.** Each block lists completion gates. Green all gates before starting the next block. (Build Plan ground rule.)
- **Pair / split markings** match Build Plan: *Pair* = both devs; *Dev A* = voice + backend (you); *Dev B* = frontend + polish.
- Every bullet cites `CLAUDE.md §X` or API Models §Y. Diverge and flag.
- Hero path is sacred — any change touching detention-escalation reruns `scripts/rehearse_hero.py` before merge.

---

## Block 0 — Foundations (Pair)

**Goal:** Confirm the bet. Externalities green before code. *(Build Plan Block 0.)*

Build Plan owns the sponsor/identity tasks. Backend-side inside Block 0:
- Decide & lock **Postgres provider** (Neon *or* Supabase, not both) — get the `DATABASE_URL` into `.env.example`.
- Decide & lock **realtime provider** (Pusher *or* Ably, not both) — get API keys into `.env.example`.
- Decide & lock **upstream fleet-data provider** — default `RELAY_ADAPTER=navpro` per 2026-04-18 changelog; `mock` is the Wi-Fi fallback. **This is missing from the Build Plan; add it to the Block 0 checklist when syncing with Dev B.**
- Claim two Twilio phone numbers: outbound caller ID (`TWILIO_FROM_NUMBER`) + inbound driver IVR (`TWILIO_INBOUND_IVR_NUMBER`).
- Create three ElevenLabs agents (`detention`, `broker_update`, `driver_ivr`) even if empty — capture their IDs into env vars now.

**Gate (backend slice):** `.env.example` fully populated; can hit ElevenLabs Agents API with `curl` using the key.

---

## Block 1 — Hello-world outbound call + shared types (Dev A voice / Dev B scaffold)

**Goal:** Prove the voice pipeline and lock the type boundary — two highest-risk items de-risked before any feature work. *(Build Plan Block 1.)*

### Dev A — Voice pipeline + FastAPI skeleton
- `backend/main.py` — app factory, CORS, lifespan (db pool open/close), request-ID middleware, structured-log middleware. (`CLAUDE.md` §3, §16)
- `backend/config.py` — Pydantic Settings; never `os.environ` in routes. (`CLAUDE.md` §10)
- `backend/deps.py` — `get_db()`, `get_adapter()`, `get_bus()` DI.
- `backend/requirements.txt` — pin: `fastapi`, `pydantic>=2`, `pydantic-settings`, `sqlalchemy>=2` async, `alembic`, `asyncpg` or `psycopg[binary]`, `httpx`, `twilio`, `pusher`, `orjson`, `python-dotenv`.
- `backend/routes/twilio.py::voice` — minimal TwiML response that `<Connect><Stream>`s to the ElevenLabs detention agent's media URL.
- `backend/services/call_orchestrator.py::place_outbound_call` — `twilio.Client.calls.create(...)` with StatusCallback + `call_id` as agent dynamic var.
- **One curl command** initiates an outbound call to a teammate's phone. Agent says its opening line audibly. *(Build Plan Block 1 Dev A gate.)*
- `GET /health` → `{status, db, pusher, adapter}` flags. 503 if DB unreachable. (`CLAUDE.md` §16)

### Dev A — Postgres + Alembic + seed loader
- Neon (or Supabase) connection via async SQLAlchemy 2.x, pool size 10.
- `alembic init backend/db/migrations`.
- `backend/models/db.py` — tables per `CLAUDE.md` §8: `drivers`, `brokers`, `loads`, `voice_calls` (JSON `transcript` + `structured_data_json`), `transcript_turns`, `detention_invoices`, `exception_events`, `webhook_events` (unique on `(provider, provider_event_id)` for idempotency). **Demo-day indexes** per §8.
- `backend/db/seed.py` — reads the 4 flat JSONs in `data/` on first boot when `drivers` empty AND `environment in {local, demo}`. **No generator — the JSONs are the canonical content.**

### Dev A + Dev B — Byte-aligned types (Pair)
- `backend/models/schemas.py` — Pydantic v2 mirroring API Models §3 + §6 + §9. `snake_case`, `str`-enums, `null → Optional[...]=None`. **Include 2026-04-19 F6b additions:** new enums `FatigueLevel`, `EtaConfidence`, `CheckinTriggerReason`; `CallPurpose += driver_proactive_checkin`; `Driver += fatigue_level, last_checkin_at, next_scheduled_checkin_at`.
- **Scope addition (2026-04-19 Build Scope lock):** `CheckinTriggerReason += missed_checkin` — fired by the anomaly detector when `now - last_checkin_at > 2 × checkin_cadence` AND the driver is not on a scheduled rest. Update API Models §2 in the same PR.
- `frontend/shared/types.ts` — TypeScript mirror, same F6b + `missed_checkin` additions.
- **`model_config = ConfigDict(extra="ignore")`** on every Pydantic model — seeds carry `_demo_notes` breadcrumbs that aren't in the schema and must not raise.

### Seed data sanity
- `data/loads.json` — 8 loads `L-12345`..`L-12352`. Hero `L-12345` matches API Models §7.1. Two loads carry `status="exception"`: L-12345 (hero) + L-12349 (fallback).
- `data/drivers.json` — 6 drivers incl. Carlos Ramirez and Miguel Rodriguez (staged F6b `hos_near_cap` target, 25-min drive clock).
- `data/brokers.json` — 5 brokers incl. Acme Logistics.
- `data/tp_parking_poi.json` — 8 POIs; hero is Pilot Needles I-40 Exit 141 (Miguel's parking target).
- Flat structure: no `data_seeding/` subfolder, no duplicates.

**Gates (Build Plan):**
- [ ] Dev A can trigger an outbound call with a single curl; agent speaks audibly.
- [ ] Dev B has the dashboard rendering all 8 seed loads in a table, styled.
- [ ] `schemas.py` ↔ `shared/types.ts` are byte-for-byte aligned (same field names, same enums, same nullability).

**Additional backend gates:**
- [ ] `alembic upgrade head && python -m backend.db.seed` → 8 loads / 6 drivers / 5 brokers in Postgres.
- [ ] `pytest -k schema_roundtrip` — every golden payload in API Models §7 round-trips through Pydantic without field loss.

---

## Block 1.5 — Adapter layer (Dev A, parallel to Dev B's Block 1 frontend scaffold)

**Goal:** Pluggable upstream fleet-data source. `navpro` is the default (2026-04-18 changelog); `mock` is the demo-day Wi-Fi fallback. *(Not in Build Plan — insert explicitly.)*

- `backend/services/adapters/base.py` — ABC mirroring API Models §9 (`list_drivers`, `get_hos`, `get_location`, `get_breadcrumbs`, `get_trip_route`, `find_nearby_places`, `create_trip`, `assign_trip`, `send_driver_message`, `start_webhook_listener`).
- `backend/services/adapters/navpro.py` — **real** httpx client against `https://api.truckerpath.com/v1`. Endpoints per API Models §4.3. Not a stub.
- `backend/services/adapters/mock_tp.py` — reads `data/*.json` + in-memory tick stream driven by `scripts/trigger_tick.py`.
- `backend/services/adapters/samsara.py` — optional, sandbox. Not on demo path.
- `backend/services/adapters/__init__.py::get_adapter()` — env-factory reading `settings.relay_adapter`; default `navpro`.

**Gate:** `get_adapter()` returns a working impl for `mock` and `navpro`. NavPro against a recorded httpx fixture is acceptable for CI; live only on rehearsal.

---

## Block 2 — The hero flow end-to-end (Pair first, then split)

**Goal:** Feature 2 (Detention Escalation Agent) working end-to-end with live transcript streaming. **Nothing else starts until green.** *(Build Plan Block 2 — "protect this flow at all costs.")*

### Pair — prompts + tool schemas
- `prompts/detention_agent.md` — three paragraphs (persona, task, constraints) + verbatim opening line.
- Attach **three P0 tools** to the detention agent config: `get_load_details`, `compute_detention_charge`, `log_conversation_outcome` (API Models §6 verbatim). *Build Plan says "five tools" — that's the old number. The remaining tools ship with their respective agents in Block 4.*

### Dev A — Tool endpoints (P0 subset)
- `backend/routes/tools.py` mounted at `POST /api/v1/agent-tools/{name}` with `X-Service-Token` dep.
- `get_load_details`, `compute_detention_charge`, `log_conversation_outcome` — idempotent on `(call_id, tool_name)` for write tools.
- Return **raw output objects**, not `{"result": ...}` wrapped.
- Hard 2-second internal deadline; timeout → `{"error": "Our systems are slow, please hold."}` (speakable).
- Structured logs per call: `event=tool_call tool=... call_id=... latency_ms=...`.
- **Latency gate:** `ab -n 100 -c 10` → p95 < 300ms.

### Dev A — Exception engine + outbound orchestrator
- `backend/services/exceptions_engine.py` — rule evaluator on every telemetry tick: detention (`arrived_at_stop_at + elapsed > threshold`), HOS (`drive_remaining ≤ 30`), ETA drift (`projected - planned ≥ 30m`). Writes `ExceptionEvent`, publishes `exception.raised`.
- `backend/routes/actions.py::escalate_detention` — API Models §4.1 verbatim. Validation order per `CLAUDE.md` §5.1: load exists → `status == "exception"` → `arrived_at_stop_at is not None` → compute expected `$` via `decimal.Decimal` → create `Call` (outcome=`in_progress`) → place call → publish `call.started` → return 202. **⚠ Math rule needs reconciliation — see "Known spec gaps" below.**
- `backend/services/call_orchestrator.py` — Twilio outbound with StatusCallback + `call_id` as agent dynamic var.

### Dev A — Webhooks with signature verification (Build Plan leaves this implicit — make it explicit)
- `backend/services/signatures.py`:
  - `verify_twilio(request, body, auth_token)` — **HMAC-SHA1** over full URL + sorted POST params.
  - `verify_elevenlabs_post_call(raw_body, header, secret)` — **HMAC-SHA256**, header format `ElevenLabs-Signature: t=<ts>,v0=<sha256>`, reject if `abs(now-ts) > 300s`. Use `hmac.compare_digest`.
  - `verify_service_token(header, expected)` — constant-time compare for `X-Service-Token`.
- `backend/routes/twilio.py::voice` — form-encoded; signature verify first; branch on `Direction` (`outbound-api` status callback vs `inbound` IVR TwiML).
- `backend/routes/elevenlabs.py::transcript` — `X-Service-Token` auth; persist only `is_final==True`; publish **every** turn (final + partial) as `call.transcript` for the dashboard shimmer.
- `backend/routes/elevenlabs.py::post_call` — HMAC verify + replay window; idempotency on `conversation_id` via `webhook_events`; branch on `event_type` (`post_call_transcription` / `post_call_audio` / `call_initiation_failure`).

### Dev A — Realtime bus
- `backend/bus/publisher.py` — Pusher HTTP REST publish, fire-and-forget, log failures. **Publish after DB commit, never before.**
- `backend/bus/channels.py` — `dispatcher.{dispatcher_id}` (single demo dispatcher = `"demo"`). The six event names per `CLAUDE.md` §9 are fixed — do NOT invent new ones.

### Dev B — Dashboard interactivity (paired scope)
- `GET /api/v1/loads/` wired; one-click Escalate button; `TranscriptPanel` subscribes to WS.

**Gates (Build Plan, strict):**
- [ ] Clicking Escalate fires a real outbound call to a teammate's receiver phone.
- [ ] Transcript appears in the dashboard panel in real time, one turn at a time.
- [ ] Call ends cleanly; `Call` record persisted with outcome.
- [ ] **Flow works ten consecutive times without failure on venue Wi-Fi.**

**Additional backend gates:**
- [ ] `pytest backend/tests/test_signatures.py` green (Twilio + ElevenLabs, including replay-reject).
- [ ] `pytest backend/tests/test_hero_flow.py` green (mocks Twilio + ElevenLabs; asserts DB state + 6 WS events).

---

## Block 3 — Invoice generation + auto paper trail + `demo_safe_mode` (Dev B PDF / Dev A hero polish)

**Goal:** The detention call produces an on-screen artifact. The call survives any upstream outage. *(Build Plan Block 3 + implicit Phase-5 safety net.)*

### Dev A — Invoice backend hook
- `backend/services/detention.py::generate_invoice(call_id)` — Decimal math, floor at 0, 2-decimal response. **Formula locked (2026-04-19):** round elapsed minutes UP to the nearest half-hour, then `billable_hours * rate_per_hour`. For the hero (167 min @ $75/h): `round(167/60 * 2)/2 = 2.5h → $187.50`. Matches API Models §7.3 golden invoice. The earlier `(elapsed - free) / 60 * rate` draft in `CLAUDE.md` §5.1 is superseded — update CLAUDE.md §5.1 step 2 in the same PR.
- Auto-invoice trigger in `post_call` webhook: when `purpose==detention_escalation` AND (`data_collection_results.receiver_accepted_detention == True` OR `ap_email != None`) → `generate_invoice(call_id)` → publish `invoice.generated`.
- Dashboard auto-opens the PDF in a modal on receipt of `invoice.generated` (Dev B wires this).

### Dev A — `demo_safe_mode` (Build Plan implicit; make explicit)
- `RELAY_DEMO_SAFE_MODE=true` branch inside `escalate_detention`: on Twilio/ElevenLabs/Pusher failure, synthesize a resolved `Call` row, load transcript from `data/fallback_transcripts/detention.json`, publish all six WS events in realistic order + timing, generate the detention invoice. Dashboard must look identical to a real run.
- Author `data/fallback_transcripts/{detention,broker_batch,driver_ivr_spanish,proactive_checkin}.json`.

### Dev A — Hero polish
- Tighten opening line, record 10 voice samples, pick best, confirm Flash v2.5 selected.
- **Record the fallback MP4** of a perfect detention call — on-the-night safety net.

### Dev B — PDF
- `@react-pdf/renderer` invoice layout: Acme header, load ref, detention minutes, rate, total, transcript footer.
- `/api/v1/invoices/{id}/pdf/` streams PDF. **Rendered in Next.js, not FastAPI.**

**Gates (Build Plan):**
- [ ] Detention call completion generates + displays the invoice PDF on screen within 3 seconds.
- [ ] PDF reads as a real document, not a hackathon mock.
- [ ] Fallback MP4 captured and playable from `/demo` page.

**Additional backend gate:**
- [ ] With Twilio auth token revoked + `RELAY_DEMO_SAFE_MODE=true`, `scripts/rehearse_hero.py` still exits 0.

---

## Block 4 — F6b Proactive Check-In + Anomaly Detection (Dev A, Feature 1 + Feature 2 from Build Scope)

**Goal:** Ship **Features 1 and 2** from the Notion Build Scope: scheduled Proactive Driver Check-In (F6b) and Anomaly Detection + Auto-Call (extends F6b). This is the new Beat 1 of the demo arc. *(Build Plan Block 4 repurposed; broker batch + inbound IVR deferred — see `[DEFERRED]` subsections below.)*

### [DEFERRED] Broker batch — moved to Later · Good-to-haves per Build Scope
- Skip `batch_broker_updates` route, `prompts/broker_update_agent.md`, broker agent ElevenLabs config, and broker fan-out WS visual for the hackathon.
- Keep the `BatchBrokerUpdatesRequest/Response` shapes in API Models §4.1 for post-hackathon resume; do **not** wire them in the frontend.
- Fallback audio snippets not recorded.

### [DEFERRED] Driver inbound IVR — moved to Later · Good-to-haves per Build Scope
- Skip the `inbound` branch of `/webhooks/twilio/voice/`, the `driver_ivr_agent` ElevenLabs config, and `prompts/driver_ivr_agent.md`.
- `record_driver_checkin` tool stays in API Models §6 for documentation; do **not** attach to any active agent.
- The outbound Proactive Check-In (below) already ships Spanish turn-taking; inbound is redundant for the judge-visible arc.
- Personalization webhook is still built for outbound (F6b), but driver-by-caller-id lookup can be skipped (outbound uses `driver_id` directly in dynamic vars).

### Dev A — F6b Proactive Driver Check-In (Feature 1 of Build Scope)
- `backend/routes/actions.py::driver_checkin` — `POST /api/v1/actions/driver-checkin/` per API Models §4.1. Errors: `409 driver_driving`, `429 checkin_too_recent`, `404 driver_not_found`.
- `backend/services/checkin_scheduler.py` — asyncio cron (1-min tick) selecting drivers where `next_scheduled_checkin_at <= now` + safety rules pass → POSTs `/actions/driver-checkin/` with `trigger_reason="scheduled"`.
- **Event triggers** from `exceptions_engine`: `hos_drive_remaining_minutes ≤ 30` → `hos_near_cap`; ETA drift ≥ 30 → `eta_drift`; extended idle at non-stop geofence → `extended_idle`. Event triggers bypass the 90-min cooldown; only `hos_near_cap` bypasses the `driver_driving` gate.
- `backend/routes/tools.py::record_proactive_checkin` — the **8th agent tool**. Idempotent on `(call_id, "record_proactive_checkin")`. Returns `{ok, next_scheduled_checkin_at, dashboard_event_emitted}`.
- **Personalization webhook enhancement** for proactive agent: on `trigger_reason == "hos_near_cap"`, pre-fetch `adapter.find_nearby_places(driver.lat, driver.lng, "parking")` and inject as `parking_nearby_json` dynamic var.
- **Post-call writeback** (in `post_call` webhook): on `purpose==driver_proactive_checkin` + `post_call_transcription`, unpack `data_collection_results` onto `Driver` row, bump `last_checkin_at = call.ended_at`, recompute `next_scheduled_checkin_at = now + 3h` (voicemail → `now + 1h`). Publish `load.updated` if on a load — **do not invent a new WS event**.
- `prompts/driver_checkin_agent.md` — warm, safety-first, HOS-aware. Caps own call length at 90s when fatigue high or HOS near cap (`hos_safety_respected` eval criterion).
- Urgent variant for anomaly triggers: opener *"Hey Miguel, haven't heard from you in a bit — everything alright?"* when `trigger_reason` is `missed_checkin`, `hos_near_cap`, `eta_drift`, or `extended_idle`. Single prompt file with `{{trigger_reason}}` templating; the scheduled opener stays warm-and-routine.
- ElevenLabs Analysis tab: 7 Data Collection items + 2 Evaluation Criteria (well under 25/30 caps).

### Dev A — Anomaly Detection (Feature 2 of Build Scope)
- `backend/services/exceptions_engine.py` gains the **missed-checkin rule** (in addition to the HOS-near-cap + ETA-drift + extended-idle rules already defined in Block 2):
  - `now - driver.last_checkin_at > 2 × checkin_cadence` AND driver is not on a scheduled rest → publish `ExceptionEvent(event_type=missed_appointment, severity=warn)` AND fire `POST /api/v1/actions/driver-checkin/` with `trigger_reason=missed_checkin`. Cadence default = 3h (same as the post-call reschedule).
- `CheckinTriggerReason` enum adds `missed_checkin` (see Block 1 schema note). Update API Models §2, `schemas.py`, and `shared/types.ts` in one PR.
- The orchestrator's 90-min cooldown is bypassed for all non-`scheduled` triggers, including `missed_checkin`.
- Dashboard surfaces a pulsing `AnomalyBadge` component on the affected driver row via the existing `exception.raised` WS event — **do not invent a new event type**. Frontend maps `event_type in {missed_appointment, hos_warning, late_eta, breakdown}` to the anomaly badge.
- Seed data staging: Miguel Rodriguez's row is seeded with `last_checkin_at = now - 5h` and `hos_drive_remaining_minutes = 25` so `scripts/trigger_tick.py --anomaly miguel` fires `hos_near_cap` + (by silence) `missed_checkin` simultaneously for a convincing live trigger.

### Dev B — Dashboard integration (Build Scope arc)
- `DriverCheckinCard` component per driver: fatigue chip, HOS three-clock mini-widget, ETA confidence, last check-in time.
- `AnomalyBadge` component: pulsing red border on the affected driver row, subscribed to `exception.raised`.
- "Check in with Miguel" one-click trigger → `POST /api/v1/actions/driver-checkin/` with `trigger_reason=manual` — the fallback path the presenter uses if the auto-anomaly doesn't fire cleanly.
- Fatigue chip + ETA confidence update on `load.updated` after post-call writeback.

**Gates (Build Scope P0):**
- [ ] Dashboard one-click trigger on Carlos or Miguel → outbound call → `record_proactive_checkin` persists → Driver row + dashboard update via `load.updated`.
- [ ] Simulated silence + HOS tick on Miguel's seeded row triggers the `AnomalyBadge` within 10 seconds (auto-anomaly path).
- [ ] Auto-anomaly fires the outbound check-in call end-to-end; Spanish conversation captures fatigue / ETA / parking-need.
- [ ] 409 `driver_driving` for non-event trigger on driving driver; 429 `checkin_too_recent` for scheduled trigger within 90 min; `hos_near_cap` / `missed_checkin` bypass both.
- [ ] `pytest backend/tests/test_proactive_checkin.py` green (incl. the new `missed_checkin` path).

**[DEFERRED] Build Plan Block 4 gates that no longer apply:**
- ~~Batch button fires 8+ simultaneous calls; dashboard shows fan-out + fan-in.~~
- ~~≥1 inbound driver call in Spanish updates the dashboard live.~~
- ~~Broker-batch fallback audio plays from `/demo`.~~

---

## Block 5 — Polish for judges (Pair; mostly frontend, minimal backend)

**Goal:** Features work; now they look inevitable. *(Build Plan Block 5.)*

Backend role is minimal — observability hygiene:
- Structured-log audit: every hot-path line is `event=... key=value`, no free-text. (`CLAUDE.md` §16)
- `/health` flags green on Fly.
- Correlation IDs flowing through Twilio/ElevenLabs/Pusher outbound calls.
- Confirm `RELAY_ADAPTER=navpro` in production env var; `mock` available via one-env-var flip.

Frontend-heavy tasks (chrome, pulse, typewriter, waveform, PDF letterhead, `/demo` page with 3 big buttons) belong to Dev B — see Build Plan for the full list.

**Gate (Build Plan):**
- [ ] A stranger looking at the dashboard for three seconds can tell which load is in exception.
- [ ] Transcript panel reads like a real phone call.
- [ ] `/demo` page fits one laptop screen with three control buttons visible.

---

## Block 6 — Submission artifacts (Pair, then split; mostly Dev B)

**Goal:** Devpost reads this, not the code. *(Build Plan Block 6.)*

Backend supports but doesn't own:
- Deploy to Fly (`iad` or `phx`, single region, `auto_stop_machines=false` for demo day).
- Pin Twilio number config (voice webhook, status callback) + each ElevenLabs agent's webhook URLs (`personalization`, `transcript`, `post-call`) at the Fly public URL. **Not ngrok.** (`CLAUDE.md` §15)
- Verify Security-tab toggles enabled on each ElevenLabs agent.
- Confirm the README architecture diagram matches the actual `backend/` tree.

**Gate (Build Plan):**
- [ ] Deck has 5 slides, no more.
- [ ] 30-second video on YouTube unlisted, linked from Devpost.
- [ ] README reads cleanly as a product page.
- [ ] Both devs rehearsed the 3-min pitch ≥2 times.

**Additional backend gate:**
- [ ] `curl https://<fly-url>/health` returns green flags; `scripts/rehearse_hero.py` against Fly URL exits 0.

---

## Block 7 — Dry runs and ruthless cuts (Pair)

**Goal:** Break it on purpose, then patch. *(Build Plan Block 7.)*

Backend focus:
- `scripts/rehearse_hero.py` end-to-end against live Twilio + ElevenLabs, 6-assertion checklist per `CLAUDE.md` §12.
- `scripts/reset_demo_state.py` — truncate calls/invoices/exceptions, reseed loads to Tuesday-afternoon state.
- `scripts/trigger_tick.py` — synthetic ELD tick to drive exceptions engine on demand.
- `scripts/serve_fallback.py` — one-keypress replay of `data/fallback_transcripts/detention.json` with realistic inter-event timing.
- **Simulate venue Wi-Fi failure** mid-detention-call: revoke Twilio auth token → `demo_safe_mode=true` synth path takes over in <1 second → dashboard looks identical. *(Build Plan gate.)*

**Gates (Build Plan):**
- [ ] Demo completes in ≤3:00 on first try, five times in a row.
- [ ] Fallback path takes <1 second.
- [ ] Non-team observer recalls the detention call without prompting.

---

## Block 8 — Ship (Pair)

**Goal:** Submit. Rest. Don't touch the code. *(Build Plan Block 8.)*

No backend action except confirming Fly app is live and webhooks still point at Fly (not ngrok). Close laptop.

**Gate:** Devpost + ElevenLabs track + any eligible sponsor track submission confirmations screenshotted.

---

## Ruthless cuts (Build Scope edition — Build Plan list superseded)

Cut in this order if any block overruns (new order reflects the Build Scope 3-feature lock):
1. **Punjabi language support** — drop `preferred_language='pa'` handling; EN + ES remain. ES is the Carlos/Miguel demo language.
2. **WhatsApp post-call summary** (F11) — out of scope regardless; don't start.
3. **Anomaly auto-trigger** — fall back to the `manual` one-click trigger for Beat 1. The `missed_checkin` rule still ships for judge Q&A, but the demo uses the button. Keep the `AnomalyBadge` visual either way.
4. **`record_proactive_checkin` full writeback** — on any failure, still publish `load.updated` with a minimal `{fatigue_level, eta_confidence}` payload so the dashboard chip updates. The invoice path is still the priority.
5. **Never cut: detention escalation (Feature 3), live transcript, invoice PDF.** If cutting the hero, the hackathon is lost.

**Already cut (2026-04-19 Build Scope):** F5 Broker Batch, F6 Inbound Driver IVR. Do not resurrect during the hackathon.

## Pivot signals (backend-relevant)

From Build Plan + our additions:
- **After Block 0 sponsor conversation:** Henry/Joe says "we're building this ourselves" → reframe pitch from "Dispatch Portal add-on" to "standalone SaaS integrating with COMMAND via webhook." Backend unchanged.
- **Partway through Block 1:** Twilio + ElevenLabs native integration won't connect → pivot to ElevenLabs WebSocket streaming + own Twilio connector. Heavy rework of `call_orchestrator.py` + `twilio.py::voice`.
- **Partway through Block 2:** Outbound call latency consistently > 1.5s → pivot hero demo to the fallback MP4 as primary.
- **New (not in Build Plan):** **NavPro API unreachable** mid-build → flip `RELAY_ADAPTER=mock` via env var; `MockTPAdapter` drives hero + all telemetry endpoints. Zero-code pivot.

---

## Cross-cutting rules (every block)

- **Schema change:** Notion API Models page first → `frontend/shared/types.ts` → `backend/models/schemas.py` → bump `X-Relay-Schema-Version`. Same PR, no partial merges.
- **New endpoint:** must exist in API Models §4 before you write it. Else stop and ask.
- **New dependency:** justify in PR description (problem it solves). No speculative libs.
- **No unrequested refactors.** Shipping > clean.
- **Hero path** is sacred — any change touching it reruns `scripts/rehearse_hero.py` before merge.
- **Seeds are canonical content, not generated.** `data/*.json` is hand-authored. `db/seed.py` only *loads*; there is no generator.

## Verification recipe (apply per block)

```bash
ruff check . && ruff format .
mypy backend/ --strict
pytest -x -q
# If hero-flow touched:
python backend/scripts/rehearse_hero.py
# If new live-call endpoint:
ab -n 100 -c 10 -p payload.json -T application/json \
   http://localhost:8000/api/v1/agent-tools/<name>   # assert p95 < 300ms
```

---

## Known spec gaps to resolve

1. **Detention formula — RESOLVED (2026-04-19).** Round elapsed minutes UP to the nearest half-hour, then `billable_hours * rate_per_hour`. Hero: 167 min → 2.5h → $187.50. Matches API Models §7.3. `CLAUDE.md` §5.1 step 2 wording is stale — update in the Block 3 freeze PR. Block 3 `detention.generate_invoice` implementation already reflects this (see the hook above).

2. **Build Plan "five tool schemas"** — stale. Current count is **8** (added `check_hos`, `lookup_parking` 2026-04-18; `record_proactive_checkin` 2026-04-19). Block 2 attaches only 3 to the detention agent. Of the remaining 5, only `check_hos` + `lookup_parking` + `record_proactive_checkin` ship (attached to the Proactive Check-In agent in Block 4); `get_driver_status` + `record_driver_checkin` stay implemented but unused per Build Scope deferrals. Keep the endpoints — they cost us nothing to have live and they answer judge Q&A cleanly.

3. **Build Plan missing F6b + anomaly detection** — the 2026-04-19 API Models changelog added F6b, and the 2026-04-19 Build Scope page promoted it plus a new anomaly detector (`missed_checkin` trigger) to Feature 1 + Feature 2 of three P0s. Block 4 in this doc now owns both. Update the Notion Build Plan in the same sync PR to match.

4. **Build Plan missing NavPro adapter step** — inserted as Block 1.5 above. Sync to the Notion Build Plan.

5. **`CLAUDE.md` §7 adapter default** — still reads as if `mock` is the default. Fix in the Block 1.5 sync PR.

6. **Build Scope drops F5/F6; Build Plan still owns them.** The Notion Build Scope page is newer and narrows P0. Block 4 of this guide now reflects Build Scope, not Build Plan. Update the Notion Build Plan Block 4 to strike broker batch + inbound IVR and insert F6b + anomaly detection. The frontend implementation guide and ElevenLabs/Twilio integration guide (sibling docs in this folder) are written against Build Scope, not Build Plan — treat them as authoritative for FE + voice plumbing until Build Plan is synced.

7. **`missed_checkin` enum addition** — Build Scope Feature 2 requires `CheckinTriggerReason += missed_checkin` in API Models §2. Not yet added to the canonical page. Land in the same PR as the anomaly detector code.
