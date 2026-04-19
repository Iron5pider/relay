# Relay — Build Scope & Cross-Session Contract

> **Who reads this:** both Claude Code sessions (FE + BE) + the human devs.
> **What it is:** the living, cross-session source of truth for features, API contract, shared types, env vars, and the demo flow.
> **What it isn't:** the *canonical* spec. The **Notion "API Models — Single Source of Truth"** page wins over this doc. If the Notion page and this file disagree, fix this file in the same push. Per-side operating rules live in `CLAUDE.md` (backend) and the frontend's equivalent.
>
> **If the code disagrees with this file, the newest changelog entry wins.** Reconcile by updating this doc before coding (see `changelog/README.md`).

---

## 1. Mission (one sentence)

Relay is an outbound voice-first exception-handling layer for small fleet dispatchers (5–50 trucks): Trucker Path telemetry → rule engine → ElevenLabs ConvAI over Twilio → live transcript + dispute-ready detention invoice on the dashboard. Demo is the product.

Full mission + context: see `CLAUDE.md` §0 and the Notion **PMD** page.

---

## 2. Sessions & lanes

- **BE session** — owns `backend/`, `data/`, `backend/scripts/`, `backend/tests/`. Operating contract: `CLAUDE.md`. Build sequence: `API_DOCS/Backend_phase_guide.md`.
- **FE session** — owns `frontend/` (Next.js 14 dashboard, `shared/types.ts`, PDF rendering via `@react-pdf/renderer`). Operating contract: the frontend's own `CLAUDE.md` / phase guide (TBD, FE session to link here on first push).

Shared-boundary artifacts (either session may edit, both must keep in sync via the same push):
- `frontend/shared/types.ts` ↔ `backend/models/schemas.py` — field-for-field mirror.
- This file (`API_DOCS/build_scope.md`).
- Every entry in `API_DOCS/changelog/`.

Neither session edits the other side's app code. If FE needs a BE change (or vice versa), say so in the changelog under **"What the other side needs to do."**

---

## 3. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Backend runtime | FastAPI + uvicorn (Python 3.11) | single process, async |
| DB | Postgres (Neon preferred; Supabase OK) | SQLAlchemy 2.x async + Alembic |
| Frontend | Next.js 14 (App Router) + TypeScript | Vercel-hosted |
| Voice | Twilio Voice + ElevenLabs ConvAI 2.0 (Flash v2.5) | Twilio → `<Connect><Stream>` to ElevenLabs |
| WebSocket bus | Pusher (default) or Ably | one channel `dispatcher.demo` |
| PDF | `@react-pdf/renderer` on the Next.js side | **FastAPI never renders PDFs** |
| Deploy | Fly.io (`iad` or `phx`) — BE; Vercel — FE | |
| Adapter default | `navpro` (per 2026-04-18 changelog) | `mock` is rehearsal fallback |

Full rationale: `CLAUDE.md` §2.

---

## 4. API contract (endpoint index)

Canonical shapes live on the Notion **API Models** page (§4 endpoints, §6 agent tools, §9 NavProAdapter types). This section is the cross-session **lookup** only. When a shape changes, update Notion → `types.ts` → `schemas.py` → this file, all in the same push.

### 4.1 Orchestration — `POST /api/v1/actions/…`

| Endpoint | Purpose | Notes |
|---|---|---|
| `/escalate-detention/` **(HERO)** | Fire outbound detention call for a load in exception | 202 `{call_id, twilio_call_sid, status, expected_detention_amount}` |
| `/batch-broker-updates/` | Fan out broker check-calls in parallel | concurrency cap = 8 |
| `/driver-checkin/` | **F6b** Outbound proactive driver check-in | safety gates: 409 `driver_driving`, 429 `checkin_too_recent` |

### 4.2 Agent tool handlers — `POST /api/v1/agent-tools/{name}` (auth: `X-Service-Token`)

| Tool | Phase | Purpose |
|---|---|---|
| `get_load_details` | P0 | Load lookup grounding |
| `compute_detention_charge` | P0 | Live $ amount |
| `log_conversation_outcome` | P0 | Agent writes outcome before hangup (idempotent) |
| `get_driver_status` | P1 | Driver telemetry + reverse-geocoded text |
| `record_driver_checkin` | P1 | **Inbound IVR** result persist (idempotent) |
| `check_hos` | P1 | Three-clock HOS snapshot |
| `lookup_parking` | P1 | Trucker Path POI |
| `record_proactive_checkin` | **F6b P0** | **Outbound** proactive check-in writeback (idempotent) |

Naming footgun: `driver_checkin` (inbound IVR) ≠ `driver_proactive_checkin` (outbound F6b). Do not collapse.

### 4.2.1 ElevenLabs agent roster (3 agents, all outbound)

| Agent | Env var | Purpose | Attached tools |
|---|---|---|---|
| `detention_agent` | `ELEVENLABS_AGENT_DETENTION_ID` | Receiver detention escalation (Beat 2, Feature 3) | `get_load_details`, `compute_detention_charge`, `log_conversation_outcome` |
| `driver_agent` | `ELEVENLABS_AGENT_DRIVER_ID` | Proactive driver check-in (Beat 1, Features 1 + 2). Renamed from `driver_checkin_agent`. | `get_driver_status`, `check_hos`, `lookup_parking`, `record_proactive_checkin`, `log_conversation_outcome` |
| `broker_update_agent` | `ELEVENLABS_AGENT_BROKER_UPDATE_ID` | Broker status calls (Feature 5); powers `/api/v1/actions/batch-broker-updates/` | `get_load_details`, `get_driver_status`, `log_conversation_outcome` |

**Deferred:** `driver_ivr_agent` (inbound IVR / Feature 6) — config and `record_driver_checkin` tool stay documented but are not provisioned, not attached to a phone number, and do not fire during the demo.

Full agent configs (voice preset, prompts, Security-tab toggles, Data Collection, Evaluation Criteria) in `API_DOCS/ElevenLabs_Twilio_integration.md` §5.

### 4.3 Webhooks

| Endpoint | Auth | Notes |
|---|---|---|
| `POST /api/v1/webhooks/twilio/voice/` | HMAC-SHA1 per Twilio | returns TwiML (XML) |
| `POST /api/v1/webhooks/elevenlabs/personalization/` | `X-Service-Token` | fires on Twilio ringback |
| `POST /api/v1/webhooks/elevenlabs/transcript/` | `X-Service-Token` | persist only `is_final==true`, publish all |
| `POST /api/v1/webhooks/elevenlabs/post-call/` | HMAC-SHA256 + replay window 300s | idempotent on `conversation_id` |

### 4.4 Dashboard reads — `GET /api/v1/…`

`/loads/`, `/loads/{id}/`, `/calls/`, `/calls/{id}/`, `/exceptions/` (SSE, 15s heartbeat), `/invoices/{id}/`, `/telemetry/driver/{id}/`, `/parking/nearby/`. PDF endpoint lives on Next.js.

---

## 5. Scope (MVP vs Stretch vs Anti-goals)

Source-of-truth priority list: `CLAUDE.md` §17.

### 5.1 MVP (P0 — must work in demo)

- FastAPI skeleton + CORS + `/health`
- Pydantic schemas ↔ `shared/types.ts` parity
- Postgres + Alembic + seed (8 loads, 6 drivers, 5 brokers)
- `MockTPAdapter` tick stream + `NavProAdapter` default
- Exception engine → `detention_threshold_breached` on hero load
- Hero escalate-detention end-to-end (Twilio + ElevenLabs + transcript + invoice + all six WS events)
- Agent tools: `get_load_details`, `compute_detention_charge`, `log_conversation_outcome`
- Twilio + ElevenLabs signature verification + replay protection
- `scripts/rehearse_hero.py` green
- `demo_safe_mode` fallback
- **F6b Proactive Check-In** (scheduler + event triggers + `record_proactive_checkin` + post-call writeback)
- **Claude anomaly agent + NavPro poller** (Sonnet 4.6 reasoning layer at the Relay ↔ NavPro seam; `backend/services/{anomaly_agent,navpro_poller,checkin_scheduler,exceptions_engine}.py`). Hard rules fire deterministically; soft signals (silence + tracking staleness + multi-signal borderlines) flow to Claude. Powers Feature 2 of the Build Scope — see `API_DOCS/Backend_phase_guide.md` Block 4 "Dev A — Anomaly Detection."

### 5.2 Stretch (P1 — add if core is solid)

- Batch broker updates with fan-out visual (agent config is P0 as of 2026-04-18 rename — `broker_update_agent` is provisioned; the **dashboard fan-out visual** is P1)
- `check_hos` + `lookup_parking`

### 5.3 Deferred (P2)

Punjabi config, LLM outcome classification, WhatsApp summary, breadcrumbs + HOS parking coordinator, SamsaraAdapter, **inbound driver IVR + `driver_ivr_agent`** (F6).

### 5.4 Anti-goals (do not build)

Multi-tenant, rate-con parsing, auth/user accounts, SIP/VoIP, production observability stack, Kubernetes / Docker Compose, PDF rendering in FastAPI, real NavPro client beyond API Models §4.3, load testing, real-API CI tests.

---

## 6. Shared types — parity rules

`backend/models/schemas.py` ↔ `frontend/shared/types.ts` must match field-for-field:

- Same casing (`snake_case`).
- Same enum string values (see the canonical enums in `CLAUDE.md` §4).
- Same nullability: Python `Optional[T] = None` ↔ TS `T | null`.
- Money: Postgres `NUMERIC(10,2)` → Pydantic `float` on the wire → `decimal.Decimal` in services. Never do float arithmetic on money.
- Seed records carry `_demo_notes` (not in schema). Pydantic sets `model_config = ConfigDict(extra="ignore")`.

F6b additions (2026-04-19): `FatigueLevel`, `EtaConfidence`, `CheckinTriggerReason` enums; `CallPurpose.driver_proactive_checkin`; `Driver.fatigue_level`, `Driver.last_checkin_at`, `Driver.next_scheduled_checkin_at`.

Anomaly-agent additions (2026-04-19): `CheckinTriggerReason.missed_checkin` (Build Scope Feature 2) + `CheckinTriggerReason.tracking_stale` (NavPro freshness signal); `Call.trigger_reasoning: Optional[str]` (Claude's plain-English rationale, surfaced verbatim in dashboard tooltip). Same-PR update: API Models §2 + §3.

---

## 7. WebSocket events

Channel: `dispatcher.demo`. Events are fixed at six — do **not** invent new event types.

1. `load.updated`
2. `exception.raised`
3. `call.started`
4. `call.transcript` (publish final + partial; persist only final)
5. `call.ended`
6. `invoice.generated`

Rule: publish **after** DB commit, never before.

---

## 8. Env vars (cross-session relevant)

Only listing vars that cross the FE/BE boundary or that either side needs to know about for config. Full BE env list: `CLAUDE.md` §10.

| Var | Side | Notes |
|---|---|---|
| `DATABASE_URL` | BE | Neon Postgres |
| `TWILIO_*` | BE | auth token used for HMAC |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_SERVICE_TOKEN`, `ELEVENLABS_WEBHOOK_SECRET` | BE | |
| `ELEVENLABS_AGENT_DETENTION_ID`, `ELEVENLABS_AGENT_DRIVER_ID`, `ELEVENLABS_AGENT_BROKER_UPDATE_ID` | BE | 3 agents per §4.2.1. `ELEVENLABS_AGENT_DRIVER_CHECKIN_ID` is the old name for `_DRIVER_ID` — rename in `.env`. `ELEVENLABS_AGENT_DRIVER_IVR_ID` commented out (deferred). |
| `PUSHER_APP_ID`, `PUSHER_KEY`, `PUSHER_SECRET`, `PUSHER_CLUSTER` | BE + FE | FE needs `PUSHER_KEY` + `PUSHER_CLUSTER` to subscribe |
| `RELAY_ADAPTER` | BE | `navpro` (default) \| `mock` \| `samsara` |
| `DEMO_SAFE_MODE` | BE | `true` → synthesize flow on upstream failure |
| `NEXT_PUBLIC_API_BASE_URL` | FE | points at Fly URL in prod |

---

## 9. Demo flow (§11 — the product)

Hero path — detention escalation for load **L-12345** (Carlos Ramirez → Receiver XYZ, Acme Logistics broker).

1. Dashboard shows L-12345 in exception (167 min past 14:00 UTC appointment, $75/hr rate, 120 free min).
2. Dispatcher clicks **Escalate Detention**. Frontend POSTs `/api/v1/actions/escalate-detention/`.
3. Backend: validate → compute expected $ → create `Call` (outcome=`in_progress`) → place Twilio call → publish `call.started`. Return 202.
4. Twilio dials the receiver's number (or `receiver_phone_override` for stage — routes to a teammate's phone).
5. On answer, Twilio `<Connect><Stream>`s to ElevenLabs detention agent. Personalization webhook fires.
6. Live turns stream via `call.transcript`. Dashboard shimmers.
7. Agent negotiates, calls `compute_detention_charge`, `log_conversation_outcome`. Receiver accepts or provides AP email.
8. Call ends. ElevenLabs post-call webhook verifies HMAC, writes transcript, publishes `call.ended`.
9. If `receiver_accepted_detention` or `ap_email` → `detention.generate_invoice(call_id)` → `invoice.generated` fires. Dashboard shows dispute-ready invoice. FE renders PDF via `@react-pdf/renderer`.

Secondary demo hooks:
- **F6b Proactive Check-In** — Carlos's `next_scheduled_checkin_at` is seeded a few minutes into the demo window; scheduler tick fires outbound call; dashboard shows fatigue chip updating live.
- **Batch broker updates** — click to fan out N calls; dashboard tiles light up one-by-one.
- **Inbound IVR** — driver calls the Twilio number in Spanish; personalization returns bilingual greeting; `record_driver_checkin` writes to dashboard.

Fallback: `scripts/serve_fallback.py` replays `data/fallback_transcripts/*.json` with realistic timing. Judges see the same UI.

---

## 10. Open questions / known gaps

Tracked in `API_DOCS/Backend_phase_guide.md` **"Known spec gaps"** section. Anything that changes schemas must land in a changelog + update Notion + this file.

1. Detention formula: `CLAUDE.md` §5.1 vs API Models §7.3 disagree. Per-half-hour rounding wins (`187.50` for the hero load). **Needs human confirmation before Phase 3 code freeze.**
2. Adapter default: `navpro` per 2026-04-18 changelog — update `CLAUDE.md` §7 wording alongside Phase 2.
3. README `shared/` path (non-blocking cleanup).
4. `.gitignore` trailing garbage (non-blocking cleanup).

---

## 11. How to evolve this file

- Schema / endpoint / env-var change → update this file **in the same push** as the code change, and reflect it in the changelog entry's **API / schema impact** section.
- Adding a new feature that the other side will see → mention it in §5 and make sure §9 still reflects what judges will experience.
- Removing something → cross it out here **and** add a changelog entry flagging the removal. Don't silently delete.
