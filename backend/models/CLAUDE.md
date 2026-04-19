# Relay — Backend (FastAPI) · `claude.md`

> **Read this file before writing a single line of code.** It is the operating contract between the human devs, Claude Code, and the Notion PMD + API Models page. If this file and the Notion page disagree, the Notion page wins — update this file in the same PR.

---

## 0. Mission

Relay is an **outbound voice-first exception-handling layer** for small fleet dispatchers (5–50 trucks). When Trucker Path driver-side data (HOS, geofence, ETA) shows trouble — a truck detaining at a receiver, an HOS cap approaching, a missed appointment — Relay **makes the phone call on the dispatcher's behalf** using ElevenLabs ConvAI + Twilio, then logs a transcript and auto-generates a dispute-ready detention invoice.

**The backend you are building is the nervous system of that loop.** It is the only component that:

1. Receives Twilio voice webhooks.
2. Receives the three ElevenLabs webhook streams (personalization / transcript / post-call).
3. Exposes the eight agent tool endpoints the ConvAI agent calls mid-conversation.
4. Orchestrates outbound calls (detention escalation, broker batch) end-to-end.
5. Talks to upstream fleet-data systems through the `NavProAdapter` interface.
6. Broadcasts live state (load updates, transcript turns, call events) to the dashboard over WebSocket.

Every other concern — dashboard UI, PDF rendering, marketing copy — lives in the Next.js frontend.

**Context:** 36-hour hackathon (Globe Hacks Season 1). Two-person team. Track: Trucker Path "Marketplace & Growth" + ElevenLabs "Voice AI" co-submission. Judging is live and interactive — judges will pick up a phone. The demo is the product.

---

## 1. Golden rules (non-negotiable)

1. **The Notion "API Models — Single Source of Truth" page is canonical.** Enum values, field names, nullability, and units come from there. If you think the page is wrong, stop and ping the human — do not silently diverge.
2. **Pydantic models in `models/schemas.py` mirror `frontend/shared/types.ts` field-for-field.** Same casing (`snake_case`), same enum string values, same nullability semantics. A schema drift between the two sides is the #1 way this project breaks on demo day.
3. **Webhooks that mutate state must verify their signature before reading the body.**
   - Twilio → HMAC-SHA1 over the full URL + sorted POST params, secret = `TWILIO_AUTH_TOKEN`.
   - ElevenLabs post-call → HMAC-SHA256 with timestamp, secret = `ELEVENLABS_WEBHOOK_SECRET`, reject if `abs(now - ts) > 300s`.
   - ElevenLabs personalization → static bearer token in `X-Service-Token`, compared with `hmac.compare_digest`.
4. **Every mutating action endpoint returns `202 Accepted` immediately** with an ID the dashboard can subscribe to. The real work happens async. The dashboard updates via WebSocket, never by polling.
5. **The agent tool handlers (`get_load_details`, `compute_detention_charge`, etc.) must be fast (<300ms) and deterministic.** They run inside a live phone call. A slow or flaky tool response is a dead conversation.
6. **Never call NavPro/Samsara/Trucker Path directly from a route or service.** Always go through `adapters.get_adapter()`. The demo runs on `MockTPAdapter`; swapping to real is a one-env-var change.
7. **Idempotency on webhooks.** Twilio and ElevenLabs retry on 5xx. Every webhook handler is a pure function of its inputs — re-delivering the same event produces the same state. Use `(provider, provider_event_id)` as a unique key.
8. **The demo path is sacred.** Detention escalation call for load `L-12345` (Carlos → Receiver XYZ) must work on the first try every single time. Any change that touches this flow requires re-running `scripts/rehearse_hero.py` end-to-end before merging.
9. **Time spent on code judges will not see is time stolen from the demo.** If you are about to spend more than 30 minutes on something not on the P0 list in §17, stop and ping the human.
10. **Fake anything a judge won't touch live.** Parking data is a static JSON snapshot. Samsara integration is a compatibility table, not a running client. Audio fallbacks are pre-recorded MP4s, not reconstructed on the fly. This is not cheating — it is scope.

---

## 2. Architecture at a glance

```
                            ┌──────────────────────┐
                            │ Next.js 14 Dashboard │   (frontend, not your concern
                            │   + shared/types.ts  │    except for WebSocket payloads)
                            └──────────┬───────────┘
                                       │ REST + WebSocket
                                       ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                  FastAPI Backend  (THIS REPO)                   │
   │                                                                 │
   │  routes/                                                        │
   │    ├── actions.py       POST /api/v1/actions/*                  │
   │    ├── tools.py         POST /api/v1/agent-tools/*              │
   │    ├── twilio.py        POST /api/v1/webhooks/twilio/voice      │
   │    ├── elevenlabs.py    POST /api/v1/webhooks/elevenlabs/*      │
   │    ├── telemetry.py     GET  /api/v1/telemetry/*  /parking/*    │
   │    └── dashboard.py     GET  /api/v1/loads /calls /exceptions   │
   │                                                                 │
   │  services/                                                      │
   │    ├── call_orchestrator.py   outbound call lifecycle           │
   │    ├── detention.py           detection + invoice trigger       │
   │    ├── batch_calls.py         parallel broker fan-out           │
   │    ├── transcript_stream.py   ingest + rebroadcast              │
   │    ├── exceptions_engine.py   rule evaluator on telemetry tick  │
   │    └── adapters/      NavProAdapter: mock | navpro | samsara    │
   │                                                                 │
   │  bus/                                                           │
   │    └── publisher.py           Pusher/Ably WS publish            │
   └───────┬───────────────────┬──────────────┬──────────────────────┘
           │                   │              │
           ▼                   ▼              ▼
   ┌─────────────┐    ┌────────────────┐  ┌────────────────┐
   │  Postgres   │    │  Twilio Voice  │  │  ElevenLabs    │
   │ (Neon/SB)   │    │   (outbound    │  │   ConvAI 2.0   │
   │             │    │    + inbound)  │  │  + Flash v2.5  │
   └─────────────┘    └────────────────┘  └────────────────┘
```

**Runtime footprint:** a single FastAPI process behind `uvicorn`, deployed on Fly.io for the hackathon. The Next.js frontend lives on Vercel and calls this service over public HTTPS. Twilio and ElevenLabs webhook URLs point directly at this service's public URL.

---

## 3. Project structure (inside `backend/`)

```
backend/
├── main.py                     # FastAPI app factory, CORS, middleware, lifespan
├── config.py                   # Pydantic Settings — env vars, one place
├── deps.py                     # FastAPI dependencies: db session, adapter, bus
│
├── routes/
│   ├── __init__.py             # router composition
│   ├── actions.py              # /api/v1/actions/escalate-detention, batch-broker-updates
│   ├── tools.py                # /api/v1/agent-tools/*   (the 6 ElevenLabs tool handlers)
│   ├── twilio.py               # /api/v1/webhooks/twilio/voice  (TwiML responses)
│   ├── elevenlabs.py           # /api/v1/webhooks/elevenlabs/{personalization,transcript,post-call}
│   ├── telemetry.py            # /api/v1/telemetry/driver/{id}, /parking/nearby
│   └── dashboard.py            # /api/v1/loads, /calls, /exceptions (SSE), /invoices/{id}
│
├── services/
│   ├── call_orchestrator.py    # place_outbound_call(), handle_call_status_callback()
│   ├── detention.py            # detention clock, invoice data assembly
│   ├── batch_calls.py          # fan-out broker check-calls w/ asyncio.gather
│   ├── transcript_stream.py    # turn-by-turn WS publish, final transcript write
│   ├── exceptions_engine.py    # rule evaluator: geofence, HOS, ETA drift
│   ├── signatures.py           # verify_twilio(), verify_elevenlabs_post_call()
│   └── adapters/
│       ├── __init__.py         # get_adapter() env-based factory
│       ├── base.py             # NavProAdapter abstract base class
│       ├── mock_tp.py          # MockTPAdapter — the demo runs on this
│       ├── navpro.py           # thin HTTP client (stubbed; env-gated)
│       └── samsara.py          # optional fallback against sandbox
│
├── models/
│   ├── schemas.py              # Pydantic: request/response + domain types
│   │                           # MUST match frontend/shared/types.ts field-for-field
│   └── db.py                   # SQLAlchemy models (or SQLModel if Dev A chooses)
│
├── bus/
│   ├── publisher.py            # publish(channel, event, payload)
│   └── channels.py             # channel name builders (dispatcher.{id}, etc.)
│
├── db/
│   ├── session.py              # engine, SessionLocal, get_db()
│   ├── migrations/             # alembic
│   └── seed.py                 # load data/*.json into Postgres on first boot
│
├── data/                       # symlink or copy of ../data/ (demo fixtures)
│   ├── loads.json
│   ├── drivers.json
│   ├── brokers.json
│   └── tp_parking_poi.json
│
├── scripts/
│   ├── rehearse_hero.py        # end-to-end detention call dry-run
│   ├── trigger_tick.py         # push a synthetic ELD tick for demo
│   └── reset_demo_state.py     # wipe calls + invoices, reseed loads
│
├── tests/
│   ├── test_agent_tools.py     # contract tests for each tool
│   ├── test_detention.py       # detention math + invoice trigger
│   ├── test_signatures.py      # HMAC verification + replay protection
│   └── test_hero_flow.py       # the demo path, mocked Twilio+ElevenLabs
│
├── pyproject.toml
├── requirements.txt            # uvicorn, fastapi, pydantic>=2, sqlalchemy, alembic,
│                               # httpx, twilio, pusher or ably, python-dotenv, orjson
├── Dockerfile
├── fly.toml
└── .env.example                # copy to .env, fill in secrets
```

---

## 4. Canonical schemas

These Pydantic models **must mirror `frontend/shared/types.ts` exactly**. Enum values, field names, optionality. If you change one, change the other in the same commit.

```python
# backend/models/schemas.py
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field

# --- primitives ---
UUID = str           # Pydantic v2: use constrained str; we validate shape, not type
ISODateTime = str    # serialized as ISO8601 Z-suffixed string; use datetime only at DB layer
E164 = str

# --- enums ---
class Language(str, Enum):
    en = "en"; es = "es"; pa = "pa"

class DriverStatus(str, Enum):
    driving = "driving"; on_duty = "on_duty"; off_duty = "off_duty"; sleeper = "sleeper"

class LoadStatus(str, Enum):
    planned = "planned"; in_transit = "in_transit"; at_pickup = "at_pickup"
    at_delivery = "at_delivery"; delivered = "delivered"; exception = "exception"

class CallDirection(str, Enum):
    outbound = "outbound"; inbound = "inbound"

class CallPurpose(str, Enum):
    detention_escalation = "detention_escalation"
    broker_check_call = "broker_check_call"
    driver_checkin = "driver_checkin"                          # inbound IVR
    driver_proactive_checkin = "driver_proactive_checkin"      # outbound scheduled / event-triggered (F6b)
    other = "other"

class CallOutcome(str, Enum):
    resolved = "resolved"; escalated = "escalated"; voicemail = "voicemail"
    no_answer = "no_answer"; failed = "failed"; in_progress = "in_progress"

class Speaker(str, Enum):
    agent = "agent"; human = "human"

class ExceptionType(str, Enum):
    detention_threshold_breached = "detention_threshold_breached"
    hos_warning = "hos_warning"
    missed_appointment = "missed_appointment"
    breakdown = "breakdown"
    late_eta = "late_eta"

class Severity(str, Enum):
    info = "info"; warn = "warn"; critical = "critical"

class InvoiceStatus(str, Enum):
    draft = "draft"; sent = "sent"; paid = "paid"; disputed = "disputed"

class UpdateChannel(str, Enum):
    call = "call"; sms = "sms"; email = "email"

class UpdateType(str, Enum):
    end_of_day = "end_of_day"; pre_delivery = "pre_delivery"; custom = "custom"

class CheckinStatus(str, Enum):
    on_route = "on_route"; at_pickup = "at_pickup"; at_delivery = "at_delivery"
    delivered = "delivered"; exception = "exception"

# Proactive Check-In agent state (F6b, added 2026-04-19)
class FatigueLevel(str, Enum):
    low = "low"; moderate = "moderate"; high = "high"; unknown = "unknown"

class EtaConfidence(str, Enum):
    on_time = "on_time"; at_risk = "at_risk"; late = "late"

class CheckinTriggerReason(str, Enum):
    scheduled = "scheduled"; hos_near_cap = "hos_near_cap"; eta_drift = "eta_drift"
    extended_idle = "extended_idle"; manual = "manual"

# --- value objects ---
class Coordinates(BaseModel):
    lat: float
    lng: float

class Stop(BaseModel):
    name: str
    lat: float
    lng: float
    phone: Optional[E164] = None
    appointment: ISODateTime

# --- domain ---
class Driver(BaseModel):
    id: UUID
    name: str
    phone: E164
    preferred_language: Language
    truck_number: str
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    # FMCSA three-clock model (minutes). All present on every response.
    hos_drive_remaining_minutes: int
    hos_shift_remaining_minutes: int
    hos_cycle_remaining_minutes: int
    hos_remaining_minutes: int         # alias of hos_drive_remaining_minutes
    status: DriverStatus
    # Proactive Check-In agent state (F6b, added 2026-04-19)
    fatigue_level: FatigueLevel                             # 'unknown' until first check-in completes
    last_checkin_at: Optional[ISODateTime] = None
    next_scheduled_checkin_at: Optional[ISODateTime] = None
    updated_at: ISODateTime

class Broker(BaseModel):
    id: UUID
    name: str
    contact_name: str
    phone: E164
    email: str
    preferred_update_channel: UpdateChannel

class DriverLite(BaseModel):
    id: UUID
    name: str
    truck_number: str

class BrokerLite(BaseModel):
    id: UUID
    name: str

class Load(BaseModel):
    id: UUID
    load_number: str
    driver: DriverLite
    broker: BrokerLite
    pickup: Stop
    delivery: Stop
    rate_linehaul: float                  # serialize with 2-decimal precision
    detention_rate_per_hour: float
    detention_free_minutes: int
    status: LoadStatus
    arrived_at_stop_at: Optional[ISODateTime] = None
    detention_minutes_elapsed: int
    exception_flags: list[ExceptionType]
    created_at: ISODateTime

class TranscriptTurn(BaseModel):
    id: UUID
    speaker: Speaker
    text: str
    language: Language
    started_at: ISODateTime
    confidence: float

class Call(BaseModel):
    id: UUID
    load_id: Optional[UUID] = None
    direction: CallDirection
    purpose: CallPurpose
    from_number: E164
    to_number: E164
    language: Language
    started_at: ISODateTime
    ended_at: Optional[ISODateTime] = None
    duration_seconds: Optional[int] = None
    outcome: CallOutcome
    audio_url: Optional[str] = None
    twilio_call_sid: str
    transcript: list[TranscriptTurn] = Field(default_factory=list)

class DetentionInvoice(BaseModel):
    id: UUID
    load_id: UUID
    call_id: UUID
    detention_minutes: int
    rate_per_hour: float
    amount_usd: float
    pdf_url: str
    status: InvoiceStatus
    created_at: ISODateTime

class ExceptionEvent(BaseModel):
    id: UUID
    load_id: UUID
    driver_id: UUID
    event_type: ExceptionType
    severity: Severity
    payload: dict
    triggered_call_id: Optional[UUID] = None
    detected_at: ISODateTime

class ParkingSpot(BaseModel):
    name: str
    lat: float
    lng: float
    available_spots: int
    distance_miles: float
    exit: str
```

**Decimal note.** Postgres stores money as `NUMERIC(10, 2)`. Pydantic serializes as `float` for API transit. Never do arithmetic in float — convert to `decimal.Decimal` at the service boundary, convert back to float at the response boundary.

---

## 5. Endpoint ownership

### 5.1 Orchestration — `routes/actions.py`

#### `POST /api/v1/actions/escalate-detention/` **(HERO)**

**Request:**

```python
class EscalateDetentionRequest(BaseModel):
    load_id: UUID
    receiver_phone_override: Optional[E164] = None   # demo staging — route to teammate's phone
    auto_invoice: bool = True
```

**Implementation contract:**

1. Validate: load exists, `status == exception`, `arrived_at_stop_at is not None`.
2. Compute detention amount = `(detention_minutes_elapsed - detention_free_minutes) / 60 * rate_per_hour`. Round to 2 decimals. Floor at 0.
3. Create `Call` row with `outcome=in_progress`, `purpose=detention_escalation`, `direction=outbound`.
4. Call `services.call_orchestrator.place_outbound_call()`:
   - Uses Twilio `client.calls.create()` with `url=` pointing at our inbound TwiML endpoint that returns `<Connect><Stream>` to ElevenLabs agent.
   - Passes `call_id` as custom metadata (via `StatusCallback` + agent dynamic var) so webhooks can correlate.
5. Publish `call.started` on `dispatcher.{dispatcher_id}` channel.
6. Return 202:

```python
class EscalateDetentionResponse(BaseModel):
    call_id: UUID
    twilio_call_sid: str
    status: Literal["initiated"] = "initiated"
    expected_detention_amount: float
```

**Errors:**
- `400 load_not_in_exception` — load not eligible.
- `404 load_not_found`.
- `502 telephony_unavailable` — Twilio or ElevenLabs failure; frontend then plays the fallback MP4.

**Demo-critical:** if `RELAY_DEMO_SAFE_MODE=true` and this endpoint fails, still write a synthetic `Call` row with `outcome=resolved` and a transcript sourced from `data/fallback_transcripts/detention.json`, and publish all WS events as if the call happened. The demo must not break.

---

#### `POST /api/v1/actions/batch-broker-updates/`

```python
class BatchBrokerUpdatesRequest(BaseModel):
    broker_ids: Optional[list[UUID]] = None        # None → all brokers on active loads
    update_type: UpdateType = UpdateType.end_of_day
    custom_message: Optional[str] = None            # required if update_type==custom

class BatchBrokerUpdatesResponse(BaseModel):
    batch_id: UUID
    call_ids: list[UUID]
    count: int
```

Implemented with `asyncio.gather` over N per-broker call placements. Cap concurrency at `settings.batch_calls_max_concurrency = 8`. Publish `call.started` individually for each — the dashboard renders them tile-by-tile for the fan-out visual.

---

#### `POST /api/v1/actions/driver-checkin/` **(F6b — Proactive Driver Check-In)**

Fires a single **outbound** Proactive Check-In call. Used by the scheduler cron and by one-click dashboard triggers. The ElevenLabs driver_checkin agent (outbound) is dispatched with dynamic variables (three-clock HOS, current load, next appointment, fatigue history, optional `parking_nearby_json`) sourced from the active `NavProAdapter` via the personalization webhook.

**Request:**

```python
class DriverCheckinRequest(BaseModel):
    driver_id: UUID
    trigger_reason: CheckinTriggerReason = CheckinTriggerReason.manual
    phone_override: Optional[E164] = None   # demo staging — route to teammate's phone
```

**Response (202):**

```python
class DriverCheckinResponse(BaseModel):
    call_id: UUID
    twilio_call_sid: str
    status: Literal["initiated"] = "initiated"
    trigger_reason: CheckinTriggerReason
```

**Orchestrator safety rules (enforced before placing the call; the agent never sees the decision):**

1. **Never call a rolling truck.** If `driver.status == "driving"` and `trigger_reason != "hos_near_cap"`, return `409 driver_driving`. FMCSA §392.82 bans handheld use while driving; hands-free Bluetooth is legal, but our scheduler is safe-by-default and waits for an on-duty-not-driving or rest window.
2. **90-minute cooldown.** If `now - driver.last_checkin_at < 90 min` and `trigger_reason == "scheduled"`, return `429 checkin_too_recent`. Event triggers (`hos_near_cap`, `eta_drift`, `extended_idle`, `manual`) bypass the cooldown.
3. **HOS parking pre-seed.** When `trigger_reason == "hos_near_cap"`, the personalization webhook pre-fetches `lookup_parking(driver.lat, driver.lng)` and injects `parking_nearby_json` as a dynamic variable so the agent can offer a parking option without a mid-call tool round-trip.
4. **Post-call bump** (in `routes/elevenlabs.py` post-call handler): unpack `data_collection_results` onto `Driver` (`fatigue_level`, `eta_confidence`, `vehicle_issues`, `vehicle_issue_notes`, `needs_parking`, `hos_self_reported_minutes`), set `last_checkin_at = call.ended_at`, recompute `next_scheduled_checkin_at = now + 3h` (configurable per carrier). On voicemail (`call_answered == false`), still bump `last_checkin_at` but shorten reschedule to `now + 1h`.

**Errors:**

- `409 driver_driving` — driver currently driving, non-event trigger; orchestrator queues for next rest window.
- `429 checkin_too_recent` — last check-in < 90 min ago and trigger is `scheduled`.
- `404 driver_not_found` — unknown `driver_id`.

**ElevenLabs Evaluation Criteria** (gate call success; see API Models §6.5):
- `fatigue_captured` — `fatigue_level != null`; if `high`, call must have included parking offer or rest recommendation.
- `hos_safety_respected` — agent did NOT prolong call past **90 seconds** when `fatigue_level == "high"` or `hos_drive_remaining_minutes < 30`. We never eat a tired driver's rest window.

---

### 5.2 Agent tool handlers — `routes/tools.py`

**These are the endpoints the ElevenLabs agent calls during a live conversation.** They must be fast (<300ms p95), deterministic, and tolerant of malformed/unknown IDs (return a helpful error object the agent can speak).

Mount each tool as `POST /api/v1/agent-tools/{tool_name}` and point the ElevenLabs tool config at the public URL. Auth via the static `X-Service-Token` header.

All eight tools and their request/response shapes are defined in API Models §6. Implement verbatim — no field drift.

| Tool | Endpoint | What it does |
|---|---|---|
| `get_load_details` | `/api/v1/agent-tools/get-load-details` | Load lookup for conversation grounding |
| `get_driver_status` | `/api/v1/agent-tools/get-driver-status` | Driver telemetry + reverse-geocoded location |
| `compute_detention_charge` | `/api/v1/agent-tools/compute-detention-charge` | Live dollar amount for the call |
| `log_conversation_outcome` | `/api/v1/agent-tools/log-conversation-outcome` | Agent writes outcome before hangup |
| `record_driver_checkin` | `/api/v1/agent-tools/record-driver-checkin` | **Inbound IVR** (driver-initiated) result → dashboard |
| `record_proactive_checkin` | `/api/v1/agent-tools/record-proactive-checkin` | **Outbound Proactive Check-In** (F6b) — fatigue / ETA / vehicle issues → Driver row + dashboard. Idempotent on `(call_id, "record_proactive_checkin")`. Returns `{ok, next_scheduled_checkin_at, dashboard_event_emitted}`. |
| `check_hos` | `/api/v1/agent-tools/check-hos` | Three-clock HOS snapshot |
| `lookup_parking` | `/api/v1/agent-tools/lookup-parking` | Trucker Path POI — the moat |

**Naming footgun:** `driver_checkin` (the existing inbound-IVR purpose + tool) and `driver_proactive_checkin` (the new outbound F6b purpose + `record_proactive_checkin` tool) are two different flows. Don't collapse them; their prompts, Data Collection schemas, and evaluation criteria are distinct.

**Location reverse geocoding** for `get_driver_status`: use a static lat/lng → human-readable map in `data/reverse_geocode.json` seeded with the demo's locations. Do not call a live geocoder — too slow, too flaky for a live call.

**`log_conversation_outcome` side-effect:** when `outcome==resolved` on a `detention_escalation` call and the post-call webhook data indicates `receiver_accepted_detention or ap_email is not None`, `services.detention.generate_invoice(call_id)` is invoked and publishes `invoice.generated`. This is what the judges see.

---

### 5.3 Twilio webhooks — `routes/twilio.py`

#### `POST /api/v1/webhooks/twilio/voice/`

- Form-encoded (not JSON). Use `Form()` parameters.
- **Verify signature first** — reject if it doesn't match. Use `services.signatures.verify_twilio()`.
- Branch on `Direction`:
  - `outbound-api` → status callback. Update `Call.outcome` / `ended_at` / `duration_seconds`. If the call ended and it was a detention call with `auto_invoice=True`, trigger invoice generation.
  - `inbound` → driver IVR entry. Return TwiML that `<Connect><Stream>`s to the ElevenLabs inbound agent's media URL, passing `call_id` (a new UUID we mint) as a custom parameter.

Response is **always** `application/xml` TwiML. Use `twilio.twiml.voice_response.VoiceResponse` to build it.

```python
@router.post("/webhooks/twilio/voice/", response_class=PlainTextResponse)
async def twilio_voice(request: Request, ...):
    body = await request.form()
    if not verify_twilio(request, body, settings.twilio_auth_token):
        raise HTTPException(403, "invalid signature")
    # ... branch + return TwiML
```

---

### 5.4 ElevenLabs webhooks — `routes/elevenlabs.py`

Three separate endpoints. Each has its own auth method. Do not unify them — ElevenLabs treats them as independent configs.

#### `POST /api/v1/webhooks/elevenlabs/personalization/`

- Fires **during the Twilio ringback** for inbound calls (driver IVR), before the driver hears anything.
- Auth: `X-Service-Token` header matches `settings.elevenlabs_service_token`.
- Look up driver by E.164 phone number in `callers.caller_id`. Resolve their active load.
- Return:

```python
class PersonalizationResponse(BaseModel):
    dynamic_variables: dict[str, str | int | None]
    first_message: Optional[str] = None      # per-call greeting override
    language: Optional[Language] = None      # per-call language override
```

**Gotcha from the Notion page:** "Per-field overrides must be toggled on in each agent's Security tab in the ElevenLabs dashboard — otherwise ElevenLabs silently ignores our response." Surface this in the Dev B onboarding checklist. Verify the toggle exists during the first end-to-end test.

#### `POST /api/v1/webhooks/elevenlabs/transcript/`

- Streams turn-by-turn during a live call.
- Auth: same `X-Service-Token`.
- Payload includes `is_final: bool`. Only persist rows where `is_final==True`. Publish **all** turns (final and partial) on WebSocket `call.transcript` for the live UI shimmer.

#### `POST /api/v1/webhooks/elevenlabs/post-call/`

- Fires after the call ends with the full transcript, `analysis.evaluation_criteria_results`, and `analysis.data_collection_results`.
- **Auth: HMAC-SHA256 signature verification, mandatory.** Use `services.signatures.verify_elevenlabs_post_call()`. Reject if `abs(now - ts) > 300s` (replay protection).
- Idempotency key: `conversation_id`. If already processed, return `200 {ok: true}` without reprocessing.
- Side-effects based on `event_type`:
  - `post_call_transcription` → write the full transcript to DB, set `Call.outcome` based on evaluation criteria, publish `call.ended`.
  - `post_call_audio` → update `Call.audio_url` once the MP3 is ready (arrives later than transcript).
  - `call_initiation_failure` → set `Call.outcome=failed`, publish `call.ended` with failure flag so the UI surfaces the fallback.

**Detention auto-invoice trigger** lives here: if `purpose==detention_escalation` and `data_collection_results.receiver_accepted_detention == True` or `ap_email != None`, call `services.detention.generate_invoice(call_id)`.

**Proactive check-in writeback (F6b)** lives here too: if `purpose==driver_proactive_checkin` and `event_type==post_call_transcription`, unpack `data_collection_results` (`fatigue_level`, `hos_self_reported_minutes`, `eta_confidence`, `vehicle_issues`, `vehicle_issue_notes`, `needs_parking`) onto the `Driver` row, bump `last_checkin_at = call.ended_at`, recompute `next_scheduled_checkin_at = now + 3h` (voicemail → `now + 1h`). Publish `load.updated` if the driver is on an active load so the dashboard reflects the new fatigue/ETA state — do **not** invent a new WS event type, the six defined in §9 cover this.

---

### 5.5 Telemetry — `routes/telemetry.py`

Thin pass-through over the active `NavProAdapter`:

- `GET /api/v1/telemetry/driver/{driver_id}/` → `adapter.getLocation()` + `adapter.getHos()`, composed into `DriverTelemetry`.
- `GET /api/v1/parking/nearby/?lat=&lng=&radius_miles=25` → `adapter.findNearbyPlaces(lat, lng, 'parking', radius)`.

Both must be callable by the agent tool handlers and by the dashboard.

---

### 5.6 Dashboard reads — `routes/dashboard.py`

The frontend may host these itself (Next.js route handlers against the DB). If it does, this module is thin. If Dev B wants FastAPI to own them, implement:

- `GET /api/v1/loads/?status=&driver_id=&has_exception=`
- `GET /api/v1/loads/{load_id}/`
- `GET /api/v1/calls/?load_id=&purpose=&outcome=&limit=&cursor=`
- `GET /api/v1/calls/{call_id}/`
- `GET /api/v1/exceptions/` → **Server-Sent Events** stream (text/event-stream). Emit `heartbeat` every 15s to keep the connection alive.
- `GET /api/v1/invoices/{invoice_id}/`

The PDF endpoint (`/invoices/{id}/pdf/`) lives on the Next.js side — Next.js uses `@react-pdf/renderer` (server-side) against invoice data fetched from this backend. FastAPI does **not** render PDFs.

---

## 6. ElevenLabs agent tool handlers — implementation notes

**Golden constraints** (they run inside a phone call, remember):

- **Latency budget: 300ms p95 at the edge.** Use indexed Postgres lookups. Pre-warm the connection pool on startup.
- **Error shape must be speakable.** If `load_id` isn't found, return `{"error": "No load found for that ID. Please check with the dispatcher."}` — the agent will read the error aloud and recover. Do **not** return 500 unless the backend itself is broken.
- **Write contracts: exactly-once semantics.** `log_conversation_outcome` and `record_driver_checkin` must be idempotent on `(call_id, tool_name)`. An agent retry after a network blip must not double-log.
- **Every tool call emits a structured log line** (`event=tool_call tool=get_load_details call_id=... latency_ms=...`). We will grep these live during the demo if anything feels off.

**Response envelope.** ElevenLabs expects the raw output object at the HTTP body level, not wrapped. Do `return GetLoadDetailsOutput(...)` directly, not `{"result": output}`.

**Location text for `get_driver_status`.** Format: `"{city}, {state}, {distance_miles:.0f} miles from {next_stop}"`. Never speak raw lat/lng — the agent will literally read the numbers out loud.

---

## 7. `NavProAdapter` pattern

Every external fleet-data source implements `services.adapters.base.NavProAdapter`. See §9 of the API Models page for the full TypeScript interface; mirror it verbatim in Python as an ABC.

```python
# services/adapters/base.py
from abc import ABC, abstractmethod

class NavProAdapter(ABC):
    @abstractmethod
    async def list_drivers(self) -> list[Driver]: ...

    @abstractmethod
    async def get_hos(self, driver_id: UUID) -> HosClocks: ...

    @abstractmethod
    async def get_location(self, driver_id: UUID) -> LocationPing: ...

    @abstractmethod
    async def get_breadcrumbs(self, driver_id: UUID, since: ISODateTime) -> list[LocationPing]: ...

    @abstractmethod
    async def get_trip_route(self, trip_id: UUID) -> TripRoute: ...

    @abstractmethod
    async def find_nearby_places(
        self, lat: float, lng: float, place_type: PlaceType, radius_miles: float = 25,
    ) -> list[ParkingSpot]: ...

    @abstractmethod
    async def create_trip(self, trip: TripUpsert) -> dict: ...

    @abstractmethod
    async def assign_trip(self, trip_id: UUID, driver_id: UUID) -> None: ...

    @abstractmethod
    async def send_driver_message(self, driver_id: UUID, text: str) -> None: ...

    @abstractmethod
    async def start_webhook_listener(self) -> None: ...
```

**Selection:**

```python
# services/adapters/__init__.py
def get_adapter() -> NavProAdapter:
    impl = settings.relay_adapter        # "mock" | "navpro" | "samsara"
    return {"mock": MockTPAdapter, "navpro": NavProAdapter,
            "samsara": SamsaraAdapter}[impl]()
```

**`MockTPAdapter` is the demo backend.** It reads from `data/*.json` + an in-memory tick stream driven by `scripts/trigger_tick.py`. It produces realistic geofence entry events on a timer so detention can fire "live" on stage.

**`NavProAdapter` (prod)** is allowed to be a stub for the hackathon — a class with each method raising `NotImplementedError("pending partner credentials")`. Demo talking track (memorize): *"The `NavProAdapter` interface is modeled on Trucker Path's documented partner contract. For the hackathon we run it against a mock service seeded with a realistic Tuesday. Flipping to the real NavPro impl is a 30-minute change once credentials arrive — the adapter boundary is exactly that thin."*

**`SamsaraAdapter`** is optional, but nice to have for Q&A: judges love seeing a real external API call work. Use the public sandbox at `developers.samsara.com`. The compatibility map is in API Models §4.3.

---

## 8. Database (Postgres)

**Provider:** Neon (preferred) or Supabase. Pick whichever gives us a connection string faster at registration.

**Connection:** single pool via `asyncpg` or `psycopg[binary]` + SQLAlchemy 2.x async. Pool size 10.

**Migrations:** Alembic. One migration per schema change. Never edit an applied migration — add a new one.

**Required tables** (SQLAlchemy models in `models/db.py`):

- `drivers`, `brokers`, `loads` — reference data. Seeded on first boot from `data/*.json`.
- `voice_calls` — every call, with JSON blob columns for `transcript` and `structured_data_json` (ElevenLabs post-call `data_collection_results`).
- `transcript_turns` — optional normalized table for turn-level queries. The JSON blob on `voice_calls` is the source of truth for the transcript.
- `detention_invoices` — generated on completion of successful detention calls.
- `exception_events` — rule-engine output, referenced by exception badge in the UI.
- `webhook_events` — `(provider, provider_event_id)` unique index for idempotency. Write every incoming webhook here before processing.

**Indexes that matter on demo day:**

- `loads (status, updated_at DESC)` — for dashboard list.
- `voice_calls (load_id, started_at DESC)` — for call history.
- `webhook_events (provider, provider_event_id)` unique — idempotency.

**Seed rule:** `db/seed.py` runs on app startup only if `drivers` table is empty. It loads `data/loads.json`, `data/drivers.json`, `data/brokers.json`. Never run in prod; gated on `settings.environment in {"local", "demo"}`.

---

## 9. WebSocket publishing (Pusher or Ably)

Pick one, commit, move on. Both work; Pusher is marginally simpler to auth for a hackathon.

- Single channel per dispatcher: `dispatcher.{dispatcher_id}`.
- In the hackathon build there is **one** dispatcher — `dispatcher_id = "demo"`. Everyone subscribes to `dispatcher.demo`.
- Events (exact names, payload shapes match API Models §5):
  - `load.updated`
  - `exception.raised`
  - `call.started`
  - `call.transcript`
  - `call.ended`
  - `invoice.generated`

```python
# bus/publisher.py
async def publish(channel: str, event: str, payload: dict) -> None:
    # Pusher HTTP REST publish. Fire-and-forget but log failures.
    ...
```

**Rule:** publish **after** the DB commit, not before. If publish fails, log and move on — the dashboard's next poll/reconnect will reconcile via `GET /api/v1/loads`.

---

## 10. Environment variables

Every env var goes through `config.py` via Pydantic Settings. Never read `os.environ` directly inside a route or service.

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    environment: str = "local"                       # local | demo | prod

    # Database
    database_url: str

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str                          # +14805551200 — our outbound caller ID
    twilio_inbound_ivr_number: str                   # +14805559999 — inbound driver line

    # ElevenLabs
    elevenlabs_api_key: str
    elevenlabs_agent_detention_id: str
    elevenlabs_agent_broker_id: str
    elevenlabs_agent_driver_ivr_id: str
    elevenlabs_service_token: str                    # shared bearer for personalization+transcript
    elevenlabs_webhook_secret: str                   # HMAC secret for post-call

    # WebSocket bus (Pusher)
    pusher_app_id: str
    pusher_key: str
    pusher_secret: str
    pusher_cluster: str = "us3"

    # Adapter selection
    relay_adapter: str = "mock"                      # mock | navpro | samsara
    navpro_api_key: str | None = None
    samsara_sandbox_key: str | None = None

    # LLM (used only for post-call analysis fallback if needed)
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None                # fallback if Anthropic rate-limits

    # Feature flags
    demo_safe_mode: bool = True                      # if primary path fails, serve canned call
    batch_calls_max_concurrency: int = 8

    class Config:
        env_file = ".env"
```

**`.env.example` ships committed.** Real `.env` is never committed — `.gitignore` it.

---

## 11. Running locally

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                   # fill in secrets

# Database
alembic upgrade head
python -m db.seed                      # loads demo fixtures

# Run
uvicorn main:app --reload --port 8000

# Expose to Twilio/ElevenLabs webhooks (dev)
ngrok http 8000
# then paste the ngrok URL into Twilio number config + ElevenLabs agent webhook fields
```

**Demo-day deployment:** Fly.io, single region (`iad` or `phx`), `fly deploy`. Point Twilio + ElevenLabs webhooks at the Fly public URL, not ngrok. Do this at least 3 hours before judging.

---

## 12. Demo rehearsal

**Before every dry-run:**

```bash
python scripts/reset_demo_state.py      # wipe calls, reseed loads to their "Tuesday afternoon" state
python scripts/rehearse_hero.py          # triggers escalate-detention, asserts the full chain works
```

`rehearse_hero.py` exercises the hero path end-to-end with the real Twilio+ElevenLabs, places the call to a known test number (teammate's phone), and asserts:

1. `Call` row created with `outcome=in_progress`.
2. At least one `call.transcript` WS event published within 10 seconds.
3. Post-call webhook received within 60 seconds.
4. `Call.outcome` set to `resolved` or `escalated`.
5. `DetentionInvoice` row created with non-zero `amount_usd`.
6. Audio URL populated within 5 minutes.

If any step fails, `exit 1`. Run this after every backend PR that touches the hero path.

**Fallback plan.** `scripts/serve_fallback.py` replays the canned `data/fallback_transcripts/detention.json` and publishes all six WS events in the correct sequence with realistic inter-event timing. If the live call fails on stage, Dev A hits one key in the terminal and the dashboard looks identical to a real run. Judges will not know.

---

## 13. Seed data

All demo state lives in `data/*.json`. Names and IDs are stable — they appear in the pitch deck, the judge Q&A doc, and the golden payloads in API Models §7. **Do not rename.**

**Flat structure.** Seeds live at `data/{brokers,drivers,loads,tp_parking_poi}.json` — single flat directory, single source of truth. Edit in place; `db/seed.py` reads the same files on boot. Future additions (`data/reverse_geocode.json`, `data/fallback_transcripts/*.json`) sit alongside at the same level.

**Extra-field convention.** Every seed record carries a `_demo_notes` string for stage rehearsal context ("hero scenario," "secondary fallback," etc.). This field is not in the canonical schema. Pydantic models **must** set `model_config = ConfigDict(extra="ignore")` so seeds load without error; never strip `_demo_notes` at seed time — they're useful when something breaks on stage.

- 8 loads, named `L-12345` through `L-12352`. **Two loads carry `status="exception"`**: L-12345 (hero — Carlos → Receiver XYZ) and L-12349 (Tommy at Phoenix DC, shipper-side detention — the designated fallback if the hero flow breaks).
- 6 drivers, including **Carlos Ramirez** (id `d1a2b3c4-0000-0000-0000-000000000001`) who anchors the hero demo. Every driver row must seed the F6b fields: `fatigue_level="unknown"`, `last_checkin_at=null`, and `next_scheduled_checkin_at` set a few minutes into the demo window for one driver (Carlos) so the Proactive Check-In fires live on stage.
- 5 brokers, including **Acme Logistics** (id `br1a2b3c-0000-0000-0000-000000000010`).
- 1 exception load: `L-12345`, Carlos → Receiver XYZ, sitting 167 minutes past a 14:00 UTC appointment, `detention_rate_per_hour=75.00`, `detention_free_minutes=120`. This is **the load** judges will see.
- `data/tp_parking_poi.json` — static snapshot of ~20 real Love's/Pilot/TA locations around I-15 and I-10 corridors. Enough for the lookup_parking tool to feel real.
- `data/fallback_transcripts/detention.json`, `.../broker_batch.json`, `.../driver_ivr_spanish.json` — canned transcripts for each of the three showcase flows.

---

## 14. Testing strategy (scoped to 36 hours)

We are not chasing 100% coverage. We are protecting the demo path and the contract boundary.

**Must have:**

- `test_signatures.py` — both Twilio and ElevenLabs signature verifiers, including replay-protection cases.
- `test_agent_tools.py` — one happy-path test per tool + one malformed-id test per tool. The malformed-id test asserts the response shape is a speakable error, not a 500.
- `test_detention.py` — detention math across edge cases (under free minutes → $0, exact free minutes → $0, partial hour → correct proration).
- `test_hero_flow.py` — mocks Twilio + ElevenLabs, walks the escalate-detention endpoint through every webhook, asserts DB state + published WS events.
- `test_proactive_checkin.py` — safety-gate tests (409 `driver_driving` when not `hos_near_cap`, 429 `checkin_too_recent` when `scheduled`), post-call Driver writeback (`fatigue_level` / `last_checkin_at` / `next_scheduled_checkin_at` update), voicemail-path 1h reschedule.

**Don't bother:**

- Full CRUD tests on dashboard endpoints.
- Migrations tests.
- Load testing. A single dispatcher will use this.
- Real API integration tests — covered by the rehearsal script, not CI.

Run with `pytest -x -q` — fail fast.

---

## 15. Failure modes and fallbacks

| Failure | Detection | Fallback |
|---|---|---|
| Twilio API returns 5xx when placing outbound call | `call_orchestrator.place_outbound_call()` raises | Return `502 telephony_unavailable`; frontend plays `demo/fallback_audio/detention_call.mp3`. If `demo_safe_mode`, also synthesize a resolved `Call` row + transcript and publish WS events as if it worked. |
| ElevenLabs agent unreachable (webhook timeouts) | Twilio call connects but agent never responds | Twilio falls back to the `statusCallback` timeout handler; we mark `Call.outcome=failed`. Frontend shows exception. |
| Post-call webhook never arrives | No `call.ended` within 2 min of Twilio `completed` status | Backfill from Twilio `StatusCallback` with minimal data; write `outcome=resolved` and empty transcript; publish `call.ended` so UI unblocks. |
| Pusher publish fails | exception in `bus/publisher.py` | Log structured error, continue. Dashboard reconciles on next mount/poll. Never block a request on pub. |
| Database down | SQLAlchemy raises on any query | `/health` returns 503. Dev A restarts Fly app. In the meantime, `demo_safe_mode` serves the canned flow from `data/` files with no DB writes. |
| Agent tool endpoint timeout mid-call | Agent hangs awkwardly | Every tool handler has a hard 2-second internal deadline. On timeout, return `{"error": "Our systems are slow, please hold."}` so the agent speaks recovery. |
| ngrok URL changes between dev and demo | Twilio webhooks 404 | Deploy to Fly before rehearsals; all webhooks point at the stable Fly URL, not ngrok. |

---

## 16. Observability (minimal but non-negotiable)

- **Structured logs.** Every log line is `logging.info("event=... key1=... key2=...")`. Searchable by `event=call_initiated call_id=...`. No free-text logs in hot paths.
- **One dashboard URL to watch.** Fly.io tail + Pusher Debug Console open on a second monitor during the demo.
- **Health endpoint.** `GET /health` → `{"status": "ok", "db": bool, "pusher": bool, "adapter": "mock"}`. Refuse to return 200 if the DB can't be reached.
- **Correlation IDs.** Every request gets `request_id = uuid4()` injected by middleware. Every log line inside a request carries it. Every outbound Twilio / ElevenLabs / Pusher call passes it.

Skip tracing, skip metrics, skip APM. You won't have time and judges won't see it.

---

## 17. Priorities (aligned with PMD)

> **Canonical sequence lives in Notion — "Build Plan (Sequential)".** That page defines blocks 0–8, pair/split pattern, completion gates, ruthless-cut cascade, and pivot signals. **`API_DOCS/Backend_phase_guide.md`** is the backend-specific checklist mapped per block (and adds Block 1.5 for the NavPro adapter + F6b Proactive Check-In work inside Block 4 — both missing from the Build Plan as of 2026-04-19 01:30). The §17 list below is **what must ship**; the Build Plan owns **when and in what order**.

**P0 — must work in the demo (Saturday 10 PM deadline):**

- [ ] FastAPI skeleton + CORS + health endpoint.
- [ ] Pydantic schemas mirroring `shared/types.ts`, cross-validated against `data/*.json` on boot.
- [ ] Postgres + Alembic + seed script, loading the 8 demo loads.
- [ ] `MockTPAdapter` with tick stream producing realistic location + HOS updates.
- [ ] `exceptions_engine` raising `detention_threshold_breached` on the hero load at T-0.
- [ ] `POST /api/v1/actions/escalate-detention/` end-to-end: Twilio dial, ElevenLabs agent, transcript stream, post-call write, invoice generation, all six WS events.
- [ ] Three ElevenLabs agent tool handlers the detention agent actually calls: `get_load_details`, `compute_detention_charge`, `log_conversation_outcome`.
- [ ] Twilio signature verification on all webhooks.
- [ ] ElevenLabs post-call HMAC verification + replay protection.
- [ ] `scripts/rehearse_hero.py` green.
- [ ] `demo_safe_mode` fallback published and tested.
- [ ] **F6b Proactive Driver Check-In.** `POST /api/v1/actions/driver-checkin/` + scheduler cron + event-trigger hooks in `exceptions_engine` (on `hos_drive_remaining_minutes ≤ 30`, ETA drift ≥ 30 min, extended idle at non-stop geofence). Orchestrator safety gates: 409 `driver_driving` unless `hos_near_cap`, 429 `checkin_too_recent` unless event-triggered. `record_proactive_checkin` tool + post-call writeback to `Driver` row + `prompts/driver_checkin_agent.md`.

**P1 — high value if core is solid:**

- [ ] `POST /api/v1/actions/batch-broker-updates/` with 3-way concurrent fan-out.
- [ ] Driver IVR inbound flow: Twilio number → ElevenLabs → `record_driver_checkin` → dashboard update.
- [ ] Personalization webhook (dynamic-vars + first_message) for multilingual warm open.
- [ ] `check_hos` + `lookup_parking` tools (needed for the driver IVR agent).

**P2 — only after P0 + P1 are solid:**

- [ ] Punjabi voice config + language detection in personalization webhook.
- [ ] Call outcome classification via Claude/GPT on post-call transcript (fills `outcome` when evaluation criteria are ambiguous).
- [ ] WhatsApp summary post-send via Twilio Conversations API.
- [ ] `get_breadcrumbs` + HOS parking coordinator (F16 from PMD).
- [ ] `SamsaraAdapter` wired up against sandbox for judge Q&A.

**Anti-goals (do not build, even if it seems easy):**

- Multi-tenant dispatcher support.
- Rate-con PDF parsing.
- Real NavPro HTTP client beyond the stub.
- Authentication / user accounts (static `X-Relay-Dispatcher-Id: demo` header is fine).
- Custom SIP or VoIP — always use ElevenLabs' native Twilio integration.
- Production observability (Sentry, Datadog, Prometheus).
- Kubernetes. Docker Compose for local if you must, Fly for prod. Nothing else.

---

## 18. Interaction patterns with Claude Code

When asked to implement a feature, follow this order every time:

1. **Re-read the relevant section of this file and the Notion API Models page.** If they disagree, stop and ask.
2. **Write the Pydantic schema first.** Validate it against the canonical TypeScript type in `shared/types.ts`. If `shared/types.ts` doesn't yet have the type, write it in the same PR.
3. **Write the service function pure.** No FastAPI imports inside `services/`. Services take domain types in and return domain types out. Routes adapt HTTP ↔ services.
4. **Write the route handler.** Thin — parse, delegate, serialize, return.
5. **Write one happy-path and one sad-path test.**
6. **If the endpoint is called during a live call, benchmark it.** `ab -n 100 -c 10` locally against the endpoint. Assert p95 < 300ms.
7. **If this touches the hero flow, run `scripts/rehearse_hero.py` before merging.**

When Claude Code proposes a refactor that wasn't asked for, the answer is no. Shipping > clean.

When Claude Code proposes adding a dependency, justify it in the PR description with the problem it solves. No speculative libs.

When Claude Code proposes a new endpoint not listed in API Models §4, stop and check with the human — it probably shouldn't exist. Every endpoint that ships was designed on the Notion page first.

---

## 19. Useful commands

```bash
# Format + lint
ruff check . && ruff format .

# Type check
mypy backend/ --strict

# Test
pytest -x -q

# Run
uvicorn main:app --reload --port 8000

# Rehearse the hero demo end-to-end
python scripts/rehearse_hero.py

# Push a synthetic tick to drive exception detection
python scripts/trigger_tick.py --load-id b17e9c2d-4a5f-4e88-9c12-a6bd2e4f7123 --minutes-past 167

# Wipe and reseed demo state
python scripts/reset_demo_state.py

# Deploy
fly deploy

# Tail prod logs
fly logs

# Explore the DB
psql $DATABASE_URL
```

---

## 20. When in doubt

- **"Should I add a feature?"** — Is it in §17 P0/P1? If no, don't.
- **"Should I refactor this?"** — Does it currently work end-to-end? If yes, don't.
- **"Should I change a schema?"** — Did you update the Notion page + `shared/types.ts` + this file in the same PR? If no, don't.
- **"Should I build a fallback?"** — Is this on the hero path? If yes, always.
- **"Should I build an admin UI, a CI pipeline, a backup job?"** — No.
- **"Is this good enough?"** — If a judge would notice the thing you're worried about in a 3-minute demo, fix it. If not, ship.

**The demo is the product. The pitch is the demo. Everything else is overhead. Build accordingly.**