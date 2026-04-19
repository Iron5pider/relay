# Tools Contract — ElevenLabs Agents ↔ Relay Backend

**Audience:** Girik (backend).
**Purpose:** Complete wire-level spec for every HTTP surface the ElevenLabs agents depend on, every webhook we receive from ElevenLabs, and the internal automation endpoints that fire after a call ends. If it's not in this doc, it's not in the demo.

**Last updated:** v1 — post agent architecture lock (3 agents: `driver_agent`, `detention_agent`, `broker_update_agent`).

---

## 0. Conventions

- **Base URL:** `{{BACKEND_URL}}` — set in `.env` (dev: `http://localhost:8000`, prod: Fly.io domain)
- **Auth:** `Authorization: Bearer {{RELAY_INTERNAL_TOKEN}}` on every tool call. Token lives in ElevenLabs as a `secret__` dynamic variable so the LLM can't leak it.
- **Content-Type:** `application/json` on all POST/PUT.
- **Response envelope:** every response is `{ "ok": bool, "data": <T> | null, "error": { "code": str, "message": str } | null }`. Agents only read `data` on success; on `ok=false` the LLM is told "I'm having trouble pulling that up" and escalates.
- **Timeouts:** see per-tool notes. Default 2s, parking/repair 5s. Any 5xx or timeout → LLM falls back to `notify_dispatcher` + transfer.
- **Idempotency:** every POST accepts optional `Idempotency-Key` header. Backend uses it for dedupe on retries. Agents don't retry — you retry server-side if needed.
- **Call ID propagation:** every tool body includes `call_id: {{system__conversation_id}}` (injected by ElevenLabs). Makes post-call stitching trivial.

---

## 1. Shared enums (source of truth)

Mirror these in `backend/models/schemas.py` as Python `Enum` classes and in `frontend/shared/types.ts` as string literal unions.

```python
class DriverCallTrigger(str, Enum):
    SCHEDULED_CHECKIN    = "scheduled_checkin"     # next_scheduled_checkin_at elapsed
    HOS_NEAR_CAP         = "hos_near_cap"          # drive clock < 45min — SAFETY
    ETA_SLIP_CHECK       = "eta_slip_check"        # projected ETA > 30min past appointment
    POST_BREAKDOWN       = "post_breakdown"        # engine-fault / driver logged issue
    STATIONARY_TOO_LONG  = "stationary_too_long"   # GPS unchanged >30min off-route
    INBOUND              = "inbound"               # driver dialed us

class Urgency(str, Enum):
    LOW  = "low"
    MED  = "med"
    HIGH = "high"  # safety-critical only

class Language(str, Enum):
    EN = "en"
    ES = "es"
    PA = "pa"

class DriverStatus(str, Enum):
    READY   = "ready"     # off-duty, available for assignment
    RESTING = "resting"   # on break, not available
    BLOCKED = "blocked"   # has a problem, not rolling
    ROLLING = "rolling"   # actively driving
    ON_DUTY = "on_duty"   # working but not driving (dock, fueling, inspection)
    DRIVING = "driving"   # same as rolling — kept for ELD parity
    OFF_DUTY = "off_duty" # 10-hour reset etc

class IssueType(str, Enum):
    MECHANICAL = "mechanical"
    PERSONAL   = "personal"
    LOAD       = "load"
    ROUTE      = "route"
    WEATHER    = "weather"
    OTHER      = "other"
    NONE       = "none"
```

---

## 2. `driver_agent` tools (8)

### 2.1 `get_driver_context`
Fetch latest driver state. Called only when dynamic vars are stale or contradict driver's claim.

```http
GET /tools/driver/context?driver_id={driver_id}
```

**Response `data`:**
```json
{
  "driver_id": "uuid",
  "name": "Carlos Ramirez",
  "first_name": "Carlos",
  "truck_number": "28",
  "current_load_id": "uuid|null",
  "last_gps": { "lat": 34.05, "lng": -118.24, "city": "Los Angeles, CA", "updated_at": "ISO8601" },
  "hos_drive_remaining_min": 210,
  "hos_shift_remaining_min": 240,
  "fuel_last_known_pct": 65,
  "preferred_language": "es",
  "fatigue_level": "moderate"
}
```
Timeout: 2s.

### 2.2 `update_hos`
```http
POST /tools/driver/update_hos
```
```json
{ "driver_id": "uuid", "call_id": "str", "hos_remaining_min": 180, "status": "driving" }
```
Response `data`: `{ "updated_at": "ISO8601" }`. Timeout: 2s.

### 2.3 `update_status`
```http
POST /tools/driver/update_status
```
```json
{ "driver_id": "uuid", "call_id": "str", "status": "ready|resting|blocked|rolling", "note": "optional" }
```
Response `data`: `{ "updated_at": "ISO8601" }`. Timeout: 2s.

### 2.4 `log_issue`
Creates an `incidents` row. Dispatcher dashboard subscribes via Supabase Realtime and shows the card immediately.

```http
POST /tools/driver/log_issue
```
```json
{
  "driver_id": "uuid",
  "call_id": "str",
  "type": "mechanical|personal|load|route|weather|other",
  "severity": 3,
  "description": "Coolant light came on 20 min ago, temp holding though"
}
```
Response `data`: `{ "incident_id": "uuid" }`. Timeout: 2s.

### 2.5 `update_eta`
```http
POST /tools/trip/update_eta
```
```json
{
  "trip_id": "uuid",
  "call_id": "str",
  "new_eta_iso": "2026-04-18T23:30:00Z",
  "reason": "Driver taking mandatory rest at Pilot Needles, ~45min delay"
}
```
Response `data`: `{ "trip_id": "uuid", "previous_eta": "ISO8601", "new_eta": "ISO8601", "delta_minutes": 45 }`. Timeout: 2s.

**Side effect:** if `abs(delta_minutes) > 30`, backend emits an internal event `eta_slip_broker_notify_candidate` — the dashboard surfaces a one-click "Notify broker" action that fires `broker_update_agent` for this single load.

### 2.6 `lookup_parking`
**Trucker Path data-moat integration.** Demo-hero tool. For the hackathon, back it with a seeded fixture of known truck stops along I-40 / I-10 / I-15 (Pilot, Love's, TA, Petro). Swap for real Trucker Path Parking API post-hackathon.

```http
GET /tools/parking/nearby?lat=34.84&lng=-114.61&radius_mi=50
```
Response `data`:
```json
[
  {
    "name": "Pilot Travel Center",
    "brand": "Pilot",
    "distance_mi": 4.2,
    "direction": "E on I-40",
    "address": "2445 W Broadway, Needles, CA",
    "amenities": ["showers", "restaurant", "fuel"],
    "est_spots_available": "likely" // "likely" | "limited" | "full" | "unknown"
  },
  ...
]
```
Max 5 results, pre-sorted by distance. Timeout: **5s**. If the agent gets 5xx or empty, it says "Nothing nearby in our system — stand by" and calls `notify_dispatcher`.

### 2.7 `find_repair_shop`
```http
GET /tools/repair/nearby?lat=34.84&lng=-114.61&service=mechanical
```
`service` ∈ `mechanical | tire | electrical | mobile_roadside | towing`.

Response `data`:
```json
[
  { "name": "TA Truck Service", "distance_mi": 6.1, "phone": "+1...", "services": ["mechanical","tire"], "hours": "24/7", "address": "..." },
  ...
]
```
Timeout: 5s. Hackathon impl: seeded JSON. Top 3 results max.

### 2.8 `notify_dispatcher`
Creates a `dispatcher_notifications` row + Supabase Realtime broadcast. Dashboard renders a toast (severity-styled).

```http
POST /tools/dispatcher/notify
```
```json
{
  "urgency": "low|med|high",
  "summary": "Carlos accepted Pilot Needles for rest, ETA pushed +45min, Acme needs update",
  "driver_id": "uuid",
  "call_id": "str",
  "load_id": "uuid|null"
}
```
Response `data`: `{ "notification_id": "uuid" }`. Timeout: 2s.

**Always call this BEFORE `transfer_to_number`** — Maria needs context before her phone rings.

---

## 3. `detention_agent` tools (5)

### 3.1 `get_rate_con_terms`
```http
GET /tools/load/rate_con_terms?load_id={load_id}
```
Response `data`:
```json
{
  "load_id": "uuid",
  "load_number": "L-12345",
  "detention_free_minutes": 120,
  "detention_rate_per_hour": 75.00,
  "tonu_rate": 150.00,
  "layover_rate": 200.00,
  "receiver_name": "Receiver XYZ",
  "receiver_address": "...",
  "appointment_dt": "2026-04-18T14:00:00Z",
  "broker_name": "Acme Logistics",
  "rate_linehaul": 2150.00
}
```
Timeout: 2s.

### 3.2 `confirm_detention`
The commit path. **Triggers the invoice-generation chain** downstream (see §6.1).

```http
POST /tools/detention/confirm
```
```json
{
  "load_id": "uuid",
  "call_id": "str",
  "ap_contact_name": "Janet Morales",
  "ap_contact_method": "email|phone|portal|unknown",
  "ap_contact_detail": "ap@receiverxyz.com",
  "supervisor_name": null,
  "committed_to_pay": true,
  "detention_hours_confirmed": 2.78,
  "notes": "Janet confirmed Net 30 standard terms, invoice PDF to ap@"
}
```
Response `data`: `{ "detention_event_id": "uuid", "invoice_generation_queued": true }`. Timeout: 2s.

### 3.3 `mark_refused`
No commitment path. No invoice generated, but still logged for the dispatcher.
```http
POST /tools/detention/refused
```
```json
{
  "load_id": "uuid",
  "call_id": "str",
  "reason": "Receiver insists detention must be handled by broker directly, refused AP routing",
  "escalation_step_reached": 3,
  "contact_attempted": "Dock supervisor Rob Jennings"
}
```
Response `data`: `{ "detention_event_id": "uuid" }`. Timeout: 2s.

### 3.4 `transcript_snapshot`
Pin a critical quote to the transcript view. Used when the agent hears a commitment or a refusal.
```http
POST /tools/call/transcript_snapshot
```
```json
{
  "call_id": "str",
  "key_quote": "Yes, we'll process the 209 through AP, send the invoice to ap@receiverxyz.com",
  "quote_type": "commitment|refusal|escalation"
}
```
Response `data`: `{ "snapshot_id": "uuid" }`. Timeout: 2s.

### 3.5 `notify_dispatcher`
Same signature as §2.8 — shared endpoint. Usage: fire BEFORE transfer on double-refusal.

---

## 4. `broker_update_agent` tools (4)

### 4.1 `get_load_status_for_broker`
Returns the broker-safe status snapshot (driver first name only, no phone, no truck location beyond city).
```http
GET /tools/load/status_for_broker?load_id={load_id}
```
Response `data`:
```json
{
  "load_id": "uuid",
  "load_number": "L-12345",
  "driver_first_name": "Carlos",
  "last_gps_city": "Needles, CA",
  "miles_remaining": 87,
  "eta_iso": "2026-04-18T22:47:00Z",
  "eta_time_pst": "3:47 PM PST",
  "appointment_time_pst": "4:00 PM PST",
  "on_schedule": true,
  "schedule_delta_minutes": -13,
  "status": "in_transit"
}
```
Timeout: 2s.

### 4.2 `mark_broker_updated`
Success path. Live answer OR voicemail — both call this.
```http
POST /tools/broker/update_confirmed
```
```json
{
  "load_id": "uuid",
  "call_id": "str",
  "broker_rep_name": "Jamie Park",
  "voicemail": false,
  "broker_ack_received": true,
  "notes": "Jamie confirmed, no follow-up needed"
}
```
Response `data`: `{ "update_id": "uuid" }`. Timeout: 2s.

### 4.3 `request_dispatcher_callback`
Broker asked to talk to a human or asked a question the agent can't answer.
```http
POST /tools/broker/escalation_request
```
```json
{
  "load_id": "uuid",
  "call_id": "str",
  "broker_rep_name": "Marcus Webb",
  "reason": "Broker wants to renegotiate detention terms on load, out of scope for status call"
}
```
Response `data`: `{ "callback_request_id": "uuid" }`. Timeout: 2s.

### 4.4 `transcript_snapshot`
Same as §3.4 — shared endpoint.

---

## 5. Call initiation — Backend → ElevenLabs

Girik's code calls ElevenLabs' REST API directly. Not a tool; this is how outbound calls start.

### 5.1 Single outbound (driver, detention, broker one-offs)

```http
POST https://api.elevenlabs.io/v1/convai/twilio/outbound-call
Authorization: xi-api-key {{ELEVENLABS_API_KEY}}
```
```json
{
  "agent_id": "{{ELEVENLABS_DRIVER_AGENT_ID}}",
  "agent_phone_number_id": "{{ELEVENLABS_PHONE_NUMBER_ID}}",
  "to_number": "+16025555612",
  "conversation_initiation_client_data": {
    "dynamic_variables": {
      "driver_id": "uuid",
      "driver_name": "Miguel",
      "truck_number": "22",
      "preferred_language": "es",
      "trigger_reason": "hos_near_cap",
      "hos_drive_remaining_minutes": 25,
      "current_load_id": "uuid",
      "fatigue_level_last_known": "unknown",
      "last_gps_city": "Needles, CA",
      "dispatcher_number": "+1...",
      "secret__relay_token": "..."
    },
    "conversation_config_override": {
      "agent": {
        "first_message": "Hola Miguel, Maya de Radar — te quedan 25 minutos de manejo. Esta llamada puede grabarse. ¿Dónde estás?"
      }
    }
  }
}
```
Returns `{ success, conversation_id, callSid }`. Store `conversation_id` — it's how you correlate the post-call webhook.

### 5.2 Batch outbound (broker 3pm check-call tsunami)

```http
POST https://api.elevenlabs.io/v1/convai/batch-calling/submit
```
```json
{
  "call_name": "broker-3pm-update-2026-04-18",
  "agent_id": "{{ELEVENLABS_BROKER_UPDATE_AGENT_ID}}",
  "agent_phone_number_id": "{{ELEVENLABS_PHONE_NUMBER_ID}}",
  "concurrency_cap": 8,
  "recipients": [
    {
      "phone_number": "+12135550010",
      "conversation_initiation_client_data": {
        "dynamic_variables": { "broker_name": "Acme Logistics", "broker_rep_first_name": "Jamie", "load_number": "L-12345", ... },
        "conversation_config_override": { "agent": { "first_message": "Hi Jamie, this is Diana from Radar Freight — quick update on load L-12345. This call may be recorded. Do you have a moment?" } }
      }
    },
    { "phone_number": "+15135550011", "conversation_initiation_client_data": { ... } },
    { "phone_number": "+15125550014", "conversation_initiation_client_data": { ... } }
  ]
}
```

**Filtering:** before building `recipients`, filter loads by `broker.preferred_update_channel == "call"`. SMS/email brokers are queued in a separate table for a stretch-goal automation (out of scope for the hackathon demo — just surface "queued" in the UI).

**Concurrency:** `concurrency_cap: 8` — Creator plan max is 10, leave 2 headroom so detention/driver calls don't 429 during the batch.

### 5.3 Cold-start mitigation
ElevenLabs agents have a 200–500ms cold-start on the first call of a session. **60 seconds before demo, fire a warm-up call to a test number and immediately hang up** for each agent. Add a cron that pings every 10 min to keep them warm during judging.

---

## 6. Post-call webhook — ElevenLabs → Backend

ElevenLabs fires `post_call_transcription` to an endpoint you configure in the dashboard. **HMAC-signed.**

### 6.1 Endpoint to expose
```http
POST {{BACKEND_URL}}/webhooks/elevenlabs/post_call
Headers:
  ElevenLabs-Signature: t=<unix_ts>,v0=<sha256_hmac>
  Content-Type: application/json
```

**Verify HMAC first. Reject if invalid.** Timestamp must be within 5 minutes of now to prevent replay.

### 6.2 Payload shape (what you'll receive)
```json
{
  "type": "post_call_transcription",
  "event_timestamp": 1745001234,
  "data": {
    "agent_id": "agent_xxx",
    "conversation_id": "conv_xxx",
    "status": "done",
    "call_duration_secs": 87,
    "transcript": [
      { "role": "agent", "message": "Hi, this is Diana with Radar Freight dispatch...", "time_in_call_secs": 0 },
      { "role": "user", "message": "Yeah, what's up?", "time_in_call_secs": 3 },
      ...
    ],
    "metadata": { "phone_call": { "direction": "outbound", "to_number": "+1...", "from_number": "+1..." } },
    "analysis": {
      "call_successful": "success|failure|unknown",
      "data_collection_results": {
        "ap_contact_name": { "value": "Janet Morales", "rationale": "..." },
        "committed_to_pay": { "value": true, "rationale": "..." },
        ...
      },
      "evaluation_criteria_results": {
        "professional_tone_maintained": { "result": "success", "rationale": "..." },
        ...
      },
      "transcript_summary": "Diana reached Janet in AP..."
    }
  }
}
```

### 6.3 Post-call fanout logic (what Girik implements)
After HMAC verify + writing the `voice_calls` row, branch on `agent_id`:

**If `agent_id == ELEVENLABS_DETENTION_AGENT_ID`:**
1. Check `data_collection_results.committed_to_pay.value == true`.
2. If yes → POST internal `/internal/invoice/generate_detention { call_id }`.
3. Regardless → emit Supabase Realtime event `voice_calls:update` so dashboard updates call card to "done".
4. If `reached_voicemail == true` → invoice still generated but with status=`awaiting_ap_confirmation`.
5. If `committed_to_pay == false` AND `escalation_step_reached == 3` → no invoice, create task card for Maria.

**If `agent_id == ELEVENLABS_DRIVER_AGENT_ID`:**
1. If `data_collection_results.issues_flagged.value == true` → POST `/internal/dispatcher/urgent_queue { call_id }`.
2. If `data_collection_results.new_eta_iso` present → the `update_eta` tool already fired mid-call, but re-verify and if missing update trip now.
3. If `escalation_requested.value == true` AND no transfer happened (agent closed instead) → create task card for Maria to callback.

**If `agent_id == ELEVENLABS_BROKER_UPDATE_AGENT_ID`:**
1. Update `load.last_broker_update_at = now()`.
2. If `voicemail.value == true` → tag with status=`vm_left` for dashboard display.
3. If `broker_ack_received == false` AND `voicemail == false` → flag for Maria retry.

---

## 7. Personalization webhook (inbound driver calls)

Fires when an unknown number dials our IVR. ElevenLabs POSTs this DURING the Twilio dial tone — you have ~3s to respond.

```http
POST {{BACKEND_URL}}/webhooks/elevenlabs/personalization
```
Incoming:
```json
{ "caller_id": "+16025555612", "agent_id": "agent_xxx", "called_number": "+1...", "call_sid": "CA..." }
```
Return (must respond within 3s or ElevenLabs uses static defaults):
```json
{
  "dynamic_variables": {
    "driver_id": "uuid",
    "driver_name": "Raj",
    "truck_number": "33",
    "preferred_language": "pa",
    "trigger_reason": "inbound",
    "current_load_id": "uuid",
    "hos_drive_remaining_minutes": 420,
    "last_gps_city": "Palm Desert, CA",
    "dispatcher_number": "+1..."
  },
  "first_message_override": "Sat Sri Akal Raj, main Maya haan — ki haal hai?"
}
```
Lookup flow: caller_id → drivers table → if found, populate; if unknown, return minimal vars + English fallback first_message: "Radar dispatch, this is Maya — who am I speaking with?"

---

## 8. Internal automation endpoints

Not called by ElevenLabs. Called by the post-call handler.

### 8.1 `/internal/invoice/generate_detention`
```http
POST {{BACKEND_URL}}/internal/invoice/generate_detention
```
```json
{ "call_id": "conv_xxx" }
```
Behavior:
1. Load `voice_calls` row by call_id, get `load_id` + `detention_hours_confirmed` + `ap_contact_*` from `analysis.data_collection_results`.
2. Pull rate_con terms (§3.1 data).
3. Build PDF with `@react-pdf/renderer` or `pdfkit`: header (Radar Freight), load info, appointment vs arrival timestamps, hours past free window, rate, total due, AP contact, transcript excerpt from `transcript_snapshot` entries.
4. Store PDF in Supabase Storage, get signed URL.
5. INSERT into `invoices` table: `{ load_id, call_id, pdf_url, amount, status: "ready_for_review", generated_at }`.
6. Supabase Realtime broadcast on channel `invoices:new`.

Response: `{ "invoice_id": "uuid", "pdf_url": "..." }`. **Target latency: <3s from post-call webhook to Realtime broadcast.** This is the demo wow moment.

### 8.2 `/internal/dispatcher/urgent_queue`
```http
POST {{BACKEND_URL}}/internal/dispatcher/urgent_queue
```
```json
{ "call_id": "conv_xxx" }
```
Behavior: pulls the call's issue details from `voice_calls.analysis.data_collection_results`, creates a `dispatcher_tasks` row with `priority=high`, broadcasts on `dispatcher_tasks:new`. Dashboard shows as a banner card requiring acknowledgment.

---

## 9. Trigger router (driver_agent outbound initiator)

Not an HTTP surface exposed to ElevenLabs — this is the internal service that decides when to fire an outbound driver call. Spec here so Girik knows the contract.

### 9.1 Anomaly detector (background job, 30s tick)
Runs via Celery beat. On each tick:

```python
for driver in active_drivers:
    if driver.hos_drive_remaining_min < 45 and driver.status == "driving":
        emit_event(type="hos_near_cap", driver_id=driver.id, severity=5)
    if now() > driver.next_scheduled_checkin_at and driver.status not in ("driving", "off_duty"):
        emit_event(type="scheduled_checkin", driver_id=driver.id, severity=2)
    if driver.gps_unchanged_for_minutes > 30 and driver.current_load.status == "in_transit":
        emit_event(type="stationary_too_long", driver_id=driver.id, severity=3)
    # ETA slip check runs per-trip:
for trip in in_transit_trips:
    projected_eta = recompute_eta(trip)
    if projected_eta > trip.appointment_dt + timedelta(minutes=30):
        emit_event(type="eta_slip_check", driver_id=trip.driver_id, trip_id=trip.id, severity=3)
```

### 9.2 Event → UI → approval → call
Events land in Supabase Realtime channel `events`. Dashboard subscribes, shows a toast:
```
⚠ Miguel Rodriguez · HOS down to 25 min on active load
[Call Miguel]   [Snooze 10 min]   [Dismiss]
```
On `[Call Miguel]` click, frontend POSTs to `/internal/call/initiate` with the event ID. Backend:
1. Looks up driver + load + builds dynamic_variables.
2. Picks the correct `first_message` template per `trigger_reason` + `preferred_language`.
3. Calls ElevenLabs outbound (§5.1).
4. Writes pending `voice_calls` row with `status=dialing`.

### 9.3 Hackathon shortcut
For demo, the "anomaly detector" is a seeded timeline file. Loading the dashboard kicks a 3-minute scripted timer that fires events at predetermined offsets (see `demo/runbook.md` once it's populated). Identical UX to a real detector; swap the timer for real rules post-demo.

---

## 10. Data model touch-points

Girik's FastAPI will CRUD these tables. Contract-critical columns only:

```sql
voice_calls (
  id UUID PK,
  conversation_id TEXT UNIQUE,   -- ElevenLabs ID
  twilio_call_sid TEXT,
  agent_id TEXT,                 -- which of the three
  driver_id UUID NULL,
  load_id UUID NULL,
  direction TEXT,                -- inbound|outbound
  trigger_reason TEXT,           -- DriverCallTrigger enum
  status TEXT,                   -- dialing|in_progress|done|failed|no_answer|voicemail
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ,
  transcript_json JSONB,
  analysis_json JSONB,           -- data_collection + evaluation
  created_at TIMESTAMPTZ DEFAULT now()
);

detention_events (id, call_id FK, load_id FK, ap_contact_*, committed_to_pay, hours_confirmed, ...);
invoices (id, load_id FK, call_id FK, pdf_url, amount, status, generated_at);
dispatcher_notifications (id, urgency, summary, driver_id, load_id, call_id, ack_at);
dispatcher_tasks (id, priority, title, body, related_call_id, status, created_at);
transcript_snapshots (id, call_id FK, key_quote, quote_type, timestamp_in_call);
incidents (id, driver_id FK, call_id FK, type, severity, description, resolved_at);
```

Publish Supabase Realtime on: `voice_calls`, `invoices`, `dispatcher_notifications`, `dispatcher_tasks`, `incidents`.

---

## 11. Build order (opinionated — for the hackathon timeline)

For Girik. In this order; nothing parallel that isn't explicitly parallel.

1. **Hour 0–2:** `.env` loaded. Twilio number claimed. ElevenLabs phone number imported. Three agents created in dashboard (empty prompts for now — just exist). Deploy FastAPI skeleton to Fly.io with `/health`.
2. **Hour 2–4:** Call initiation §5.1 working. Fire a single outbound to your own phone with stubbed `driver_agent`. Hear "Hi, this is Maya." Hang up. ✅ if audio is μ-law 8kHz clean.
3. **Hour 4–6:** Post-call webhook §6 receiving + HMAC verified + `voice_calls` row writes. Inspect payload shape for real.
4. **Hour 6–10:** Tools §2.1–2.8 implemented against seed data. `update_hos`, `lookup_parking`, `notify_dispatcher` are demo-critical — do those three first; others after.
5. **Hour 10–14:** `detention_agent` tools §3 + post-call invoice chain §8.1. This is the HERO path — fully test with a recorded call end-to-end: dial Carlos's fake receiver → transcript → webhook → invoice PDF in storage → dashboard toast.
6. **Hour 14–18:** `broker_update_agent` tools §4 + batch §5.2. Test with 3 recipients firing simultaneously.
7. **Hour 18–22:** Trigger router §9 + personalization webhook §7 + driver IVR inbound E2E test.
8. **Hour 22–28:** Polish, fallback audio, demo rehearsal.

## 12. Gotchas (learned from the research doc — don't re-learn)

- **Voicemail does not fire `call_initiation_failure`.** Either enable Twilio AMD (`MachineDetection=Enable`) or let the agent detect silence + VM keywords and call `end_call`. Our agents handle VM inline — but AMD gives you `AnsweredBy` in the webhook which helps route post-call.
- **`conversation_config_override` requires toggles to be enabled per-field in Security tab.** Dashboard → Agent → Security → "Allow first_message override" MUST be checked. Otherwise ElevenLabs silently ignores overrides. This is the #1 first-time bug.
- **Concurrency caps:** Creator plan = 10 concurrent calls, Pro = 20. Batch at 8 leaves headroom for detention+driver calls that need to fire during the batch.
- **Cold start:** 200–500ms on first call of a session. Warm-up cron every 10 min during judging hours.
- **System prompt tokens:** keep under 1500 tokens (≈6KB) per agent. Every extra KB = 20–40ms latency.
- **`apply_text_normalization: false` on live phone calls** — text normalization adds latency and corrupts currency ("$209" → "two hundred nine dollars" voiced correctly anyway via Flash v2.5).
- **Data collection schema hard cap: 25 fields per agent.** Evaluation criteria hard cap: 30. We're under budget on both.
- **Dynamic variable prefix `secret__`** hides it from the LLM. Use for auth tokens. Not `_secret`, not `private_` — literally `secret__` with two underscores.
- **Audio format:** Twilio native integration negotiates μ-law 8kHz automatically. If you roll your own `<Stream>` integration, you MUST set `output_format: "ulaw_8000"` explicitly or audio is garbled.

---

**If anything in this doc is ambiguous, flag it — don't guess.** Prompts and agent config are owned by the ElevenLabs lead; backend/tools are owned by Girik. Breaking-change protocol: any field change here updates this file + `backend/models/schemas.py` + `frontend/shared/types.ts` in the same PR.
