# Relay — ElevenLabs + Twilio Integration Guide

> **Who reads this:** Dev A (voice + backend) primarily; Dev B (frontend) for the WS event shapes. Claude Code uses it as the voice-plumbing reference.
>
> **Precedence:** Notion **API Models** (canonical contracts, §4.1 webhooks + §6 tool schemas + §6.5 Data Collection + §9 Adapter) · Notion **Build Scope** (3 P0 features; F5 broker batch and F6 inbound IVR deferred) · `backend/models/CLAUDE.md` §5.3 + §5.4 + §6 · this doc. On conflict, the Notion pages win.
>
> **Scope note (2026-04-18 rename).** The ElevenLabs surface is **three agents** total, all outbound:
> 1. **`detention_agent`** — receiver detention escalation (Beat 2, Feature 3).
> 2. **`driver_agent`** — outbound proactive driver check-in (Beat 1, Features 1 + 2). Renamed from `driver_checkin_agent`.
> 3. **`broker_update_agent`** — outbound broker status calls (powers `/api/v1/actions/batch-broker-updates/`). Active/provisioned even if the dashboard doesn't click it during the scripted demo; judges may ask to see it.
>
> `driver_ivr_agent` (inbound IVR) remains **deferred** per the 2026-04-19 Build Scope narrowing. Config is kept in documentation for post-hackathon resume; it is not provisioned, not attached to a live phone number, and not tested.

---

## 1. Architecture at a glance

```
┌──────────────┐   REST    ┌───────────────────────┐                       ┌────────────────────┐
│  Next.js UI  │──────────▶│  FastAPI (this repo)  │                       │   Twilio Voice     │
│  + Pusher WS │◀──────────│  routes/actions.py    │──── calls.create ────▶│  outbound number   │
└──────────────┘           │  routes/tools.py      │                       │  +14805551200      │
      ▲                    │  routes/twilio.py     │◀── voice webhook ─────│                    │
      │ WS                 │  routes/elevenlabs.py │  (TwiML + status cb)  │  inbound number    │
      │ (dispatcher.demo)  │  services/            │                       │  +14805559999†     │
      │                    │   ├─ call_orchestrator│                       └─────────┬──────────┘
      │                    │   ├─ signatures       │                                 │
      │                    │   └─ adapters/        │                                 │ media
      │                    └─────────┬─────────────┘                                 │ stream
      │                              │                                               ▼
      │                              │ tool call (HTTP)                ┌────────────────────────┐
      │                              │◀─────────────────────────────── │  ElevenLabs ConvAI 2.0 │
      │                              │                                  │  Flash v2.5            │
      │                              │ personalization webhook (pre-call) │  3 agents (demo):     │
      │                              │ transcript webhook (during call)  │   · detention_agent   │
      │                              │ post-call webhook (after call)    │   · driver_agent      │
      │                              │                                  │   · broker_update_agent│
      │                              │                                  └────────────────────────┘
      │                              ▼
      │                   Pusher HTTP publish (after DB commit)
      └────── Pusher client ◀── dispatcher.{id} channel
```

`†` inbound Twilio number stays provisioned as the outbound caller ID; the inbound IVR routing path is not wired per Build Scope deferral of F6.

**Ownership split.**
- **Twilio is our telephony carrier** — buys the phone number, dials the PSTN endpoint, streams audio.
- **ElevenLabs is our voice agent** — runs the LLM + TTS + ASR loop, calls our tools mid-conversation, emits webhooks.
- **Relay's FastAPI backend** is the glue: initiates outbound calls via the Twilio SDK, serves TwiML that `<Connect><Stream>`s to the ElevenLabs agent, answers the agent's tool calls, and processes the three ElevenLabs webhook streams.
- **The ElevenLabs ↔ Twilio integration is "native"** (set up on the ElevenLabs dashboard under Phone Numbers). We do **not** run a custom SIP/VoIP layer. Do not build one.

---

## 2. Account + workspace prerequisites (Block 0)

**Twilio.**
- Trial or paid account; project `relay-hack-2026`.
- **Two phone numbers** bought (same account, same project):
  - `TWILIO_FROM_NUMBER` — outbound caller ID. Appears as the "from" on detention + check-in calls.
  - `TWILIO_INBOUND_IVR_NUMBER` — provisioned but only rings a voicemail hand-off per Build Scope deferral of F6. Keep it so we can point to a distinct inbound channel in Q&A.
- Voice webhook fields on the inbound number can be left pointed at Twilio's default IVR handler for the hackathon; we don't receive inbound calls in the demo.
- **Auth token** = `TWILIO_AUTH_TOKEN`. **Do not rotate during demo week.** The HMAC-SHA1 verifier on incoming webhooks uses this secret.

**ElevenLabs.**
- Creator-tier or higher (ConvAI 2.0 requires it).
- **Three agents created** on the ElevenLabs dashboard → Conversational AI (all outbound, all Maya voice + Flash v2.5):
  1. `detention_agent` — receiver detention escalation.
  2. `driver_agent` — proactive driver check-in. One agent serves both the scheduled routine check-ins AND the anomaly-urgent variant — prompt templates on `trigger_reason`. Renamed from `driver_checkin_agent`.
  3. `broker_update_agent` — broker status calls; powers `/api/v1/actions/batch-broker-updates/`.
- **`driver_ivr_agent`** (inbound IVR) — deferred per Build Scope. Do not create. If an earlier stub exists, leave it disabled and do not attach a phone number.
- Each agent's ID goes into `.env`:
  - `ELEVENLABS_AGENT_DETENTION_ID`
  - `ELEVENLABS_AGENT_DRIVER_ID` (renamed from `ELEVENLABS_AGENT_DRIVER_CHECKIN_ID`)
  - `ELEVENLABS_AGENT_BROKER_UPDATE_ID`
- Phone-number provisioning on ElevenLabs: use the native Twilio integration. In each agent's Phone Numbers tab, connect the Twilio account (provide SID + auth token) and assign the outbound `TWILIO_FROM_NUMBER` to all three outbound agents. ElevenLabs will handle the SIP trunking under the hood.
- **Voice preset (Maya):** warm, Southwest-neutral female. Stability `0.55`. Similarity `0.80`. Flash v2.5 latency target `<75ms` first-token. If a voice isn't labeled "Maya" in the library, clone a similar preset and name it Maya for consistency in logs.

**Env vars shipped in `.env.example`** (secrets filled in `.env`, never committed):

```bash
# Twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=+14805551200
TWILIO_INBOUND_IVR_NUMBER=+14805559999

# ElevenLabs
ELEVENLABS_API_KEY=
ELEVENLABS_AGENT_DETENTION_ID=
ELEVENLABS_AGENT_DRIVER_ID=                # renamed from ELEVENLABS_AGENT_DRIVER_CHECKIN_ID
ELEVENLABS_AGENT_BROKER_UPDATE_ID=         # active; powers batch broker updates
ELEVENLABS_SERVICE_TOKEN=                  # shared bearer for personalization + transcript
ELEVENLABS_WEBHOOK_SECRET=                 # HMAC-SHA256 secret for post-call

# Deferred (not in demo — kept documented for post-hackathon resume)
# ELEVENLABS_AGENT_DRIVER_IVR_ID=          # inbound IVR; deferred per Build Scope
```

**Rename history.**
- `ELEVENLABS_AGENT_DRIVER_CHECKIN_ID` → `ELEVENLABS_AGENT_DRIVER_ID` (this push).
- `ELEVENLABS_AGENT_BROKER_ID` (original name in an early `.env.example`) → `ELEVENLABS_AGENT_BROKER_UPDATE_ID` (this push, and re-activated after being deferred).

---

## 3. Outbound call lifecycle (the hot path)

Both P0 outbound flows (detention + driver check-in) share this sequence. Differences are in the agent config and the payloads, not the plumbing.

> **Trigger source note (2026-04-18).** Outbound `driver_agent` calls may be triggered by either the hard rule engine OR the Claude anomaly agent (`backend/services/anomaly_agent.py`). The `DriverCheckinRequest` payload gains an optional `trigger_reasoning` field that the scheduler fills with Claude's rationale or the hard rule's label; everything downstream (orchestrator, TwiML, ElevenLabs dynamic vars, transcripts) is identical. See `Backend_phase_guide.md` Block 4 "Dev A — Anomaly Detection" for the split.

### 3.1 Trigger → call placed

1. FE POST → `/api/v1/actions/escalate-detention/` or `/api/v1/actions/driver-checkin/`.
2. `routes/actions.py` validates the request (API Models §4.1 error surface: 400/404/409/429/502) and creates a `voice_calls` row with `outcome=in_progress`, `direction=outbound`, correct `purpose`.
3. `services/call_orchestrator.py::place_outbound_call(call_id, agent_id, to_number)`:
   - Builds the outbound dial via `twilio.rest.Client(...).calls.create(...)`.
   - Sets `url=<our_public_base>/api/v1/webhooks/twilio/voice/` — Twilio fetches TwiML from here when the call connects.
   - Sets `status_callback=<our_public_base>/api/v1/webhooks/twilio/voice/` with `status_callback_event=['initiated', 'ringing', 'answered', 'completed']`. Same path — we branch on `Direction` and `CallStatus`.
   - Sets `machine_detection='DetectMessageEnd'` so we get `AnsweredBy=machine_*` in the callback when the answerer is voicemail. The ElevenLabs agent can keep talking, but we flag the call row for voicemail-path post-processing.
   - Passes `call_id` as a Twilio custom parameter (`statusCallbackEvent` includes our `call_id` via query string on the callback URL) AND as an ElevenLabs **agent dynamic variable** so the agent echoes it into tool calls.
4. Twilio returns a `CallSid`. We persist it onto the `voice_calls` row.
5. BE publishes `call.started` on `dispatcher.demo` **after** DB commit. FE's `CallStatusBanner` transitions from `calling → connected`.

### 3.2 Answer → TwiML → media stream

1. On answer, Twilio GETs/POSTs to our `/webhooks/twilio/voice/` endpoint.
2. We **verify the Twilio signature first** (HMAC-SHA1 over the full URL + sorted POST params, secret = `TWILIO_AUTH_TOKEN`). Reject on failure (403). See §6.1.
3. We return TwiML:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <Response>
     <Connect>
       <Stream url="wss://api.elevenlabs.io/v1/convai/conversation?agent_id={AGENT_ID}">
         <Parameter name="call_id" value="{OUR_CALL_UUID}" />
         <Parameter name="purpose" value="detention_escalation" />
         <Parameter name="trigger_reason" value="manual" />    <!-- only on driver-checkin -->
       </Stream>
     </Connect>
   </Response>
   ```

   Build with `twilio.twiml.voice_response.VoiceResponse` — never hand-concatenate XML strings.

4. Twilio `<Connect><Stream>` bridges the call's media into ElevenLabs's WebSocket. The agent takes over.

### 3.3 Personalization webhook (pre-agent-speech)

ElevenLabs fires `POST /api/v1/webhooks/elevenlabs/personalization/` **during the Twilio ringback**, before the agent speaks. This is where we inject dynamic variables and (for bilingual starts) a `first_message` override.

- **Auth:** `X-Service-Token: ${ELEVENLABS_SERVICE_TOKEN}`. Compare with `hmac.compare_digest`. 403 on mismatch.
- **Request:**

  ```json
  {
    "caller_id": "+13105551234",       // on inbound only; for outbound we receive our own FROM_NUMBER
    "agent_id": "agent_abc123",
    "called_number": "+13105551234",
    "call_sid": "CA123..."
  }
  ```

  Outbound calls: the `Stream` `<Parameter>` block we set in TwiML is what ElevenLabs uses to resolve our `call_id` → the associated load / driver / purpose. We look up that context in our DB and compose the dynamic-vars response.

- **Response shape** (API Models §4.1 `/webhooks/elevenlabs/personalization/`):

  ```json
  {
    "dynamic_variables": {
      "driver_name": "Carlos Ramirez",
      "driver_language": "es",
      "current_load_number": "L-12345",
      "current_stop_name": "Receiver XYZ",
      "eta_minutes": 0,
      "hos_drive_remaining_minutes": 210,
      "parking_nearby_json": null
    },
    "first_message": "Hola Carlos, soy Maya. ¿Cómo va todo?",
    "language": "es"
  }
  ```

- **Per-purpose dynamic variables (always populated on the response):**

  | Purpose | Dynamic vars injected |
  |---|---|
  | `detention_escalation` | `load_number`, `driver_name`, `broker_name`, `receiver_name`, `minutes_at_stop`, `rate_per_hour`, `detention_free_minutes`, `expected_detention_amount` |
  | `driver_proactive_checkin` (`trigger_reason=scheduled`) | `driver_name`, `driver_language`, `current_load_number`, `next_stop_name`, `eta_minutes`, `hos_drive_remaining_minutes`, `hos_shift_remaining_minutes`, `hos_cycle_remaining_minutes`, `last_checkin_at`, `parking_nearby_json=null` |
  | `driver_proactive_checkin` (`trigger_reason=hos_near_cap`) | same, plus `parking_nearby_json` — pre-fetched via `adapter.find_nearby_places(driver.lat, driver.lng, 'parking', 25)` at personalization time so the agent can offer parking without a mid-call tool round-trip |
  | `driver_proactive_checkin` (`trigger_reason in {missed_checkin, eta_drift, extended_idle, manual}`) | same as scheduled, but the agent prompt template opens with the urgent variant (*"Hey {driver_name}, haven't heard from you in a bit — everything alright?"*) selected by the `trigger_reason` dynamic var |

- **`first_message` override gotcha.** ElevenLabs silently ignores `first_message` and `language` unless the matching **Security-tab override toggles** are enabled on the agent. Verify once, per agent, when first wiring up. Symptom if you miss it: the agent opens in English regardless of what we send. Fix is a dashboard toggle, not a code change.

- **Latency target:** respond in <200ms. Personalization blocks the agent's first utterance. Use `get_adapter().find_nearby_places` **async-concurrently** with the DB lookup when `trigger_reason=hos_near_cap`; don't serialize.

### 3.4 Tool calls (mid-conversation)

While the agent is speaking/listening, it autonomously calls our tool endpoints. Each tool:
- Is mounted at `POST /api/v1/agent-tools/{tool-name}`.
- Is authenticated with `X-Service-Token`.
- Returns the **raw output object** (not wrapped in `{result: ...}`). See `backend/models/CLAUDE.md` §6.
- Has a hard **2-second internal deadline**; on timeout, return `{"error": "Our systems are slow, please hold."}` — speakable by the agent.
- Emits a structured log: `event=tool_call tool=<name> call_id=<uuid> latency_ms=<n>`.

**Tool roster and active agents:**

| Tool | `detention_agent` | `driver_agent` | `broker_update_agent` | Ships? |
|---|:---:|:---:|:---:|:---:|
| `get_load_details` | ✅ | — | ✅ | yes |
| `compute_detention_charge` | ✅ | — | — | yes |
| `log_conversation_outcome` | ✅ | ✅ | ✅ | yes |
| `get_driver_status` | — | ✅ | ✅ | yes (endpoint live; attached to `driver_agent` + `broker_update_agent`) |
| `check_hos` | — | ✅ | — | yes |
| `lookup_parking` | — | ✅ | — | yes |
| `record_proactive_checkin` | — | ✅ | — | yes (P0 per F6b) |
| `record_driver_checkin` | — | — | — | **endpoint implemented for documentation; NOT attached to any active agent** — inbound IVR deferred per Build Scope |

The ElevenLabs agent config (Tools tab) for each agent lists only the checkmarked tools. Adding extras pollutes the tool-choice space and lengthens latency — leave the agent configs minimal.

**Response latency constraint** (`CLAUDE.md` §6): p95 < 300ms at the edge. Verify with `ab -n 100 -c 10` before Block 2 close. Indexed Postgres lookups on `loads(id)`, `drivers(id)`, `voice_calls(id)`. Pre-warm the connection pool on app startup.

**Error shape must be speakable.** If `load_id` isn't found: `{"error": "No load found for that ID. Please check with the dispatcher."}`. The agent reads it aloud. **Never** return 500 unless the backend itself is broken — returning 500 in a live call kills the conversation.

**Reverse geocoding for `get_driver_status`.** Use a static lookup table in `data/reverse_geocode.json` seeded with the 8 demo locations. Do not call a live geocoder — it's slow and flaky on venue Wi-Fi. Agent reads `"Phoenix, AZ, 370 miles from Los Angeles"`, never `"33.45, -112.07"`.

### 3.5 Transcript webhook (during call)

ElevenLabs streams turn-by-turn transcripts to `POST /api/v1/webhooks/elevenlabs/transcript/`.

- **Auth:** `X-Service-Token`.
- **Payload:**
  ```json
  {
    "call_id": "c91e...",
    "speaker": "agent",
    "text": "Hi, this is Maya...",
    "language": "en",
    "started_at": "2026-04-18T16:47:13Z",
    "confidence": 1.0,
    "is_final": false
  }
  ```
- **Persist only when `is_final=true`** to `transcript_turns` + the `voice_calls.transcript` JSON blob.
- **Publish every turn** (final and partial) on `call.transcript` WS — the dashboard shimmer wants the partials.
- Short-circuit cost: if `speaker=agent` and `is_final=false`, you can skip the DB write and just publish.

### 3.6 Post-call webhook (after call)

`POST /api/v1/webhooks/elevenlabs/post-call/` fires after the call ends. It is the authoritative source for:
- Final transcript.
- `analysis.evaluation_criteria_results` (e.g. `invoice_path_unblocked` for detention, `fatigue_captured` for check-in).
- `analysis.data_collection_results` (the structured fields we told ElevenLabs to extract — see §6.5 of API Models).

**Auth — HMAC-SHA256, mandatory.** ElevenLabs sends `ElevenLabs-Signature: t=<unix_ts>,v0=<sha256_hmac>`. Verify:

```python
import hmac, hashlib, time

def verify_elevenlabs_post_call(raw_body: bytes, header: str, secret: str) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(","))
    ts, sig = parts["t"], parts["v0"]
    if abs(time.time() - int(ts)) > 300:   # replay protection, 5 minutes
        return False
    expected = hmac.new(
        secret.encode(), f"{ts}.".encode() + raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig)
```

Read the header, read the **raw body bytes** (not the parsed JSON — the signature is over the exact bytes), verify, then parse. If the framework parsed the body before handing you the request, re-serialize and signature will fail — FastAPI's `request.body()` returns the raw bytes; use that.

**Event types we handle** (API Models §4.1):
- `post_call_transcription` — the main one. Write transcript, set outcome, trigger downstream side-effects.
- `post_call_audio` — MP3 URL arrives later than the transcript. Update `Call.audio_url`.
- `call_initiation_failure` — rare (dial failed). Mark `Call.outcome=failed`; publish `call.ended` with a failure flag for the FE to surface the fallback.

**Idempotency.** `conversation_id` is the dedup key. Write an entry in `webhook_events (provider='elevenlabs', provider_event_id=conversation_id)` with a unique index; on conflict, return `200 {ok: true}` without reprocessing. Same pattern for Twilio status callbacks keyed on `CallSid + CallStatus`.

**Side-effects by purpose:**

| `Call.purpose` | Post-call side-effects |
|---|---|
| `detention_escalation` | Write transcript + structured data. If `data_collection_results.receiver_accepted_detention == true` OR `ap_email != null` → `services.detention.generate_invoice(call_id)` → publish `invoice.generated`. Set `Call.outcome` from `evaluation_criteria_results.invoice_path_unblocked` (success → `resolved`, failure → `escalated`). |
| `driver_proactive_checkin` | Unpack `data_collection_results` (`fatigue_level`, `hos_self_reported_minutes`, `eta_confidence`, `vehicle_issues`, `vehicle_issue_notes`, `needs_parking`) onto the `Driver` row. Set `last_checkin_at = call.ended_at`. Recompute `next_scheduled_checkin_at = now + 3h`; if `data_collection_results.call_answered == false` (voicemail), shorten to `now + 1h`. Publish `load.updated` if driver on an active load (the FE's `DriverCheckinCard` subscribes). |
| `broker_check_call` | Active (`broker_update_agent`). Write transcript + structured data. Set `Call.outcome` from `evaluation_criteria_results.broker_informed` (success → `resolved`; failure → `escalated`). No invoice side-effect. Publish `call.ended`. |
| `driver_checkin` (inbound) | **deferred.** Handler exists for post-hackathon; does not fire in the demo because the inbound agent isn't wired to a phone number. |

**Publish after DB commit.** Always. If Pusher fails, log and move on — the dashboard will reconcile on next mount.

### 3.7 Status callback (Twilio-side call lifecycle)

Twilio fires status callbacks on `initiated / ringing / answered / completed` to the same `/webhooks/twilio/voice/` endpoint with `Direction=outbound-api`. We branch on `CallStatus`:

| CallStatus | Handler behavior |
|---|---|
| `initiated`, `ringing` | No-op (we already published `call.started` on the trigger). |
| `answered` | No-op — the ElevenLabs bridge handles it. |
| `in-progress` | No-op. |
| `completed` | Update `voice_calls.ended_at`, `duration_seconds`. Do NOT set outcome from here — wait for ElevenLabs `post_call_transcription`. If post-call doesn't arrive within 2 minutes, backfill minimal data and publish `call.ended` so the FE unblocks. |
| `failed`, `busy`, `no-answer`, `canceled` | `Call.outcome = failed`. Publish `call.ended`. If `RELAY_DEMO_SAFE_MODE=true`, fall through to the canned transcript path (see §9). |

**Signature verification required on every status callback** (HMAC-SHA1). If signature invalid → 403 + do not update state.

---

## 4. Inbound IVR (deferred per Build Scope — documented only)

Pre-Build-Scope this was Feature 6 of the PMD. With the 2026-04-19 scope narrowing, inbound IVR is **off the demo path**. The `driver_ivr_agent` config, `record_driver_checkin` tool, and inbound Twilio webhook branch remain in code + documentation for post-hackathon resume. **None of them fire during the demo.**

If you (or a future dev) wants to re-enable:
1. Set the inbound Twilio number's voice webhook to `<public>/api/v1/webhooks/twilio/voice/`. We already branch on `Direction=inbound`.
2. Return TwiML with `<Connect><Stream>` to the ElevenLabs `driver_ivr_agent` media URL.
3. The personalization webhook already handles the inbound branch (driver-by-caller-id lookup). Enable driver lookup by uncommenting the branch in `routes/elevenlabs.py::personalization`.
4. Attach `get_driver_status`, `record_driver_checkin`, `check_hos`, `lookup_parking` to the agent's Tools tab.
5. Add an inbound-specific prompt in `prompts/driver_ivr_agent.md` (warm, patient, auto-language detect).

Until then, the number rings to Twilio's default IVR (voicemail) and no Relay logic runs.

---

## 5. Agent configuration (ElevenLabs dashboard)

Each agent's dashboard config has four relevant tabs: **Voice**, **Prompt**, **Tools**, **Analysis**, **Security**. ElevenLabs caps enforcement:

- **25 Data Collection items per agent**
- **30 Evaluation Criteria per agent**

Our agents use well below both. See Analysis tab specs below.

### 5.1 `detention_agent` (outbound, Feature 3)

- **Voice:** Maya, Flash v2.5, stability 0.55, similarity 0.80.
- **Prompt:** `prompts/detention_agent.md`. Three paragraphs (persona, task, constraints). Verbatim opening line from Demo Script:
  > *"Hi, this is Maya calling from Acme Trucking on behalf of {driver_name}. Our driver has been at your dock {minutes_at_stop_text} past his {appointment_local} window. Per rate con, detention begins at {rate_per_hour:,.0f} dollars per hour after {detention_free_minutes/60:.0f} hours. Can you connect me with shipping, or should I route the invoice to AP?"*
- **Tools:** `get_load_details`, `compute_detention_charge`, `log_conversation_outcome`. (3 of 8.)
- **Security:** enable `first_message` override, `language` override, `dynamic_variables` override. (All three toggles.)
- **Analysis — Data Collection (4 items, well under 25 cap):**
  - `receiver_accepted_detention: boolean`
  - `ap_email: string | null`
  - `expected_departure_minutes: number | null`
  - `reason_for_delay: string | null`
- **Analysis — Evaluation Criteria (1 of 30):**
  - `invoice_path_unblocked`: success iff `receiver_accepted_detention == true` OR `ap_email != null`.

### 5.2 `driver_agent` (outbound, Feature 1 + 2)

> Renamed from `driver_checkin_agent` — same agent, same role, shorter name. Keep the new file name `prompts/driver_agent.md`; the old file should be moved (not copied) in the same PR as the code rename.

- **Voice:** same Maya preset. Stability bumped to 0.60 for warmer routine feel; keep 0.55 if A/B testing.
- **Prompt:** `prompts/driver_agent.md`. Templated on `trigger_reason`:
  - `scheduled` → *"Hola {driver_name}, soy Maya. ¿Cómo va todo?"* (warm opener)
  - `hos_near_cap` → *"Hola {driver_name}, te quedan {hos_drive_remaining_minutes} minutos de manejo. ¿Necesitas parking cerca?"* (urgent but calm)
  - `missed_checkin` / `eta_drift` / `extended_idle` → *"Hola {driver_name}, no hemos hablado en un rato — ¿todo bien?"* (gentle concern)
  - `manual` → same as `scheduled` (presenter-driven button click)
  - All prompts define: 90-second soft cap if `fatigue_level == 'high'` or `hos_drive_remaining_minutes < 30` (the `hos_safety_respected` eval criterion).
- **Tools:** `get_driver_status`, `check_hos`, `lookup_parking`, `record_proactive_checkin`, `log_conversation_outcome`. (5 of 8.)
- **Security:** enable `first_message`, `language`, `dynamic_variables` override toggles.
- **Analysis — Data Collection (7 items):**
  - `fatigue_level: enum low|moderate|high` — map driver's 1–10 → low(1–3)/moderate(4–7)/high(8–10).
  - `hos_self_reported_minutes: number | null`
  - `eta_confidence: enum on_time|at_risk|late`
  - `vehicle_issues: boolean`
  - `vehicle_issue_notes: string | null`
  - `needs_parking: boolean`
  - `call_answered: boolean` — false on voicemail-only outcomes.
- **Analysis — Evaluation Criteria (2):**
  - `fatigue_captured`: success iff `fatigue_level != null`; if `high`, call must include parking offer OR rest recommendation.
  - `hos_safety_respected`: agent did NOT prolong call past 90s when `fatigue_level == 'high'` or `hos_drive_remaining_minutes < 30`.

### 5.3 `driver_ivr_agent` (inbound, **NOT wired in demo**)

Config exists for completeness and judge Q&A. Not attached to an inbound number during the demo. See §4 for re-enable steps.

- **Voice:** Maya, Flash v2.5.
- **Prompt:** `prompts/driver_ivr_agent.md`. Warm, patient, auto-language detect.
- **Tools (if re-enabled):** `get_driver_status`, `record_driver_checkin`, `check_hos`, `lookup_parking`.
- **Analysis — Data Collection items** (6, from API Models §6.5): `reported_location`, `checkin_status`, `exception_type`, `hos_self_reported_minutes`, `fuel_level_pct`, `needs_parking`.

### 5.4 `broker_update_agent` (outbound, Feature 5)

Active. Directly calls brokers on behalf of the dispatcher — end-of-day status, pre-delivery ETA confirmation, or a custom message — via `/api/v1/actions/batch-broker-updates/`. Whether the dashboard clicks the Batch button during the scripted demo is FE's call; the agent is wired either way so judges can exercise it in Q&A.

- **Voice:** Maya, Flash v2.5, stability 0.55, similarity 0.80 (same preset as detention).
- **Prompt:** `prompts/broker_update_agent.md`. Brief, factual, professional — no small talk. Opening template:
  > *"Hi, this is Maya calling from Acme Trucking on behalf of {driver_name} on load {load_number}. Current status: {status_summary}. ETA to delivery: {eta_text}. Anything else you need from us?"*
  On voicemail, leave a 15-second summary: load #, driver, ETA, callback number.
- **Tools:** `get_load_details`, `get_driver_status`, `log_conversation_outcome`. (3 of 8.)
- **Security:** enable `first_message`, `language`, `dynamic_variables` override toggles.
- **Analysis — Data Collection (3 items, well under 25 cap):**
  - `broker_acknowledged: boolean` — did the broker verbally acknowledge the ETA, or was a voicemail left with load# + ETA?
  - `broker_requested_followup: boolean` — did the broker ask for any downstream action?
  - `broker_notes: string | null` — free-text of anything the broker flagged.
- **Analysis — Evaluation Criteria (1 of 30):**
  - `broker_informed`: success iff `broker_acknowledged == true` OR a voicemail was left that included load# + ETA.
- **Concurrency note.** Creator-tier ElevenLabs caps concurrency at ~5 parallel calls. `batch_broker_updates` uses `asyncio.Semaphore(settings.batch_calls_max_concurrency)` with default `8` — lower to `5` if rate-limit errors appear during rehearsal. See §14 open questions.

---

## 6. Signature verification (every inbound webhook)

One module — `backend/services/signatures.py` — three functions. Every webhook handler calls the appropriate one **before** reading the request body as JSON/form.

### 6.1 Twilio (HMAC-SHA1)

```python
# services/signatures.py
from twilio.request_validator import RequestValidator

def verify_twilio(request, form_data: dict, auth_token: str) -> bool:
    validator = RequestValidator(auth_token)
    # Twilio signs the full URL (scheme://host/path?query) + sorted form params
    url = str(request.url)
    signature = request.headers.get("X-Twilio-Signature", "")
    return validator.validate(url, form_data, signature)
```

Twilio's SDK ships the validator. Don't reimplement. Reject (403) on any mismatch.

**Gotcha:** on Fly.io (and other reverse-proxied setups), the `request.url` scheme may be `http` even though Twilio hit `https`. Force scheme normalization:

```python
url = str(request.url).replace("http://", "https://", 1) if request.headers.get("x-forwarded-proto") == "https" else str(request.url)
```

### 6.2 ElevenLabs post-call (HMAC-SHA256 + replay window)

```python
import hmac, hashlib, time

def verify_elevenlabs_post_call(raw_body: bytes, header: str, secret: str, max_age_s: int = 300) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        ts, sig = parts["t"], parts["v0"]
    except (KeyError, ValueError):
        return False
    if abs(time.time() - int(ts)) > max_age_s:
        return False
    expected = hmac.new(
        secret.encode(), f"{ts}.".encode() + raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig)
```

- **Raw body** — FastAPI: `raw = await request.body()` before any parsing.
- **Replay window** — 300s (5 minutes). Reject older.
- **Constant-time compare** — `hmac.compare_digest`, not `==`.

### 6.3 ElevenLabs personalization / transcript (static bearer)

```python
def verify_service_token(header: str, expected: str) -> bool:
    return hmac.compare_digest(header or "", expected)
```

Header: `X-Service-Token: ${ELEVENLABS_SERVICE_TOKEN}`. Same secret on both endpoints — don't fragment.

**Test cases** (in `backend/tests/test_signatures.py`, P0 per `CLAUDE.md` §14):
- Valid Twilio signature → pass.
- Tampered POST body → fail.
- Valid ElevenLabs post-call signature → pass.
- Timestamp 10 minutes old → fail (replay protection).
- Wrong `X-Service-Token` → fail.
- Missing `ElevenLabs-Signature` header → fail without crashing.

---

## 7. Data flow by demo beat

### Beat 1 — Driver check-in + anomaly (Feature 1 + 2)

```
1. exceptions_engine.py tick detects hos_near_cap on Miguel (seeded state).
2. Publishes exception.raised on dispatcher.demo. FE AnomalyBadge pulses red.
3. exceptions_engine POSTs /api/v1/actions/driver-checkin/ with trigger_reason=hos_near_cap.
4. routes/actions.py::driver_checkin:
     - Safety gates pass (hos_near_cap bypasses 90-min cooldown + driving check).
     - Creates voice_calls row (outcome=in_progress, purpose=driver_proactive_checkin).
5. call_orchestrator.place_outbound_call(agent_id=DRIVER_AGENT, to=miguel.phone).
     - Twilio calls Miguel's phone.
     - Publishes call.started on Pusher.
6. Twilio answer → fetches TwiML from /webhooks/twilio/voice/.
     - Signature verified. TwiML returns <Connect><Stream> to ElevenLabs driver_agent.
7. ElevenLabs personalization webhook fires:
     - Dynamic vars: driver_name=Miguel, driver_language=es, hos_drive_remaining_minutes=25,
       parking_nearby_json=<Pilot Needles POI>, trigger_reason=hos_near_cap.
     - first_message override → Spanish urgent opener.
8. Agent speaks Spanish opener. Live transcript streams via /webhooks/elevenlabs/transcript/.
     - Publishes call.transcript per turn (final + partial).
9. Agent calls check_hos (if it wants a second confirmation) and lookup_parking
     (often skipped — we pre-seeded parking_nearby_json).
10. Agent conducts the fatigue / ETA / parking-need conversation.
11. Agent calls record_proactive_checkin with structured data.
12. Agent calls log_conversation_outcome with outcome=resolved.
13. Call ends → Twilio status callback CallStatus=completed.
14. ElevenLabs post-call webhook fires (HMAC verified):
      - Writes transcript + structured data.
      - Unpacks data_collection_results onto Driver row (fatigue_level=moderate, etc).
      - last_checkin_at = call.ended_at.
      - next_scheduled_checkin_at = now + 3h.
      - Publishes load.updated → FE DriverCheckinCard chip animates.
      - Publishes call.ended.
```

### Beat 2 — Detention escalation → auto-invoice (Feature 3)

```
1. Presenter clicks Escalate on L-12345.
2. FE POSTs /api/v1/actions/escalate-detention/ { load_id, auto_invoice: true }.
3. routes/actions.py::escalate_detention:
     - Validates load exists, status=exception, arrived_at_stop_at non-null.
     - Computes expected detention (Decimal math, half-hour rounding up → $187.50).
     - Creates voice_calls row.
4. call_orchestrator places Twilio outbound call to receiver phone
     (or receiver_phone_override = teammate's phone for stage).
     - Publishes call.started.
5. Twilio answer → TwiML → ElevenLabs detention_agent media stream.
6. Personalization webhook:
     - Dynamic vars: load_number, driver_name=Carlos, broker_name=Acme Logistics,
       receiver_name=Receiver XYZ, minutes_at_stop=167, rate_per_hour=75,
       detention_free_minutes=120, expected_detention_amount=187.50.
7. Agent opens with the verbatim detention line (personalization injects vars).
8. Agent calls get_load_details (grounding).
9. Receiver (teammate) responds. Transcript streams live.
10. Agent calls compute_detention_charge (reads $187.50 aloud).
11. Receiver: "Yes, send it to ap@receiverxyz.com." → agent extracts ap_email
     to Data Collection post-call.
12. Agent calls log_conversation_outcome(outcome=resolved, follow_up=false).
13. Call ends. Twilio status callback.
14. ElevenLabs post-call webhook (HMAC verified):
      - Writes transcript.
      - Reads analysis.data_collection_results.ap_email == "ap@receiverxyz.com".
      - invoice_path_unblocked criterion: success.
      - Triggers services.detention.generate_invoice(call_id).
      - generate_invoice writes DetentionInvoice row, renders signed PDF URL.
      - Publishes invoice.generated → FE InvoiceModal auto-opens with $187.50.
      - Publishes call.ended.
```

---

## 8. Idempotency + retries

**Both providers retry on 5xx / timeouts.** Our job:

- **Idempotency keys:**
  - Twilio: `(CallSid, CallStatus)` — a completed callback redelivered twice must not double-update.
  - ElevenLabs post-call: `conversation_id`.
  - Agent tool writes: `(call_id, tool_name)` — a tool retry after a network blip must not double-log.
- **Storage:** `webhook_events` table with a unique index on `(provider, provider_event_id)`. Insert-or-conflict pattern; on conflict return `200 {ok: true}` without reprocessing.
- **Return fast on retry.** Don't re-run expensive side-effects (invoice generation, Driver row update) after a hit on the idempotency key.

**What NOT to be idempotent on:** WS publishes. Pushing `call.ended` twice is harmless (FE dedups by `call_id`). Don't add complexity for the zero-cost-of-failure case.

---

## 9. `demo_safe_mode` (belt-and-suspenders)

If any of Twilio / ElevenLabs / Pusher fails during the demo, `RELAY_DEMO_SAFE_MODE=true` takes over. The dashboard must look **identical** to a real run.

**Detention flow safe-mode path** (`routes/actions.py::escalate_detention`):

```python
try:
    twilio_call_sid = await call_orchestrator.place_outbound_call(...)
except (TwilioException, ElevenLabsException, PusherException) as e:
    if not settings.demo_safe_mode:
        raise HTTPException(502, "telephony_unavailable") from e
    # Safe-mode synth path
    return await synthesize_detention_flow(call_id, load)

async def synthesize_detention_flow(call_id, load):
    """
    Replays data/fallback_transcripts/detention.json over 28 seconds
    with realistic inter-turn timing, publishing all six WS events.
    Generates the detention invoice at the end. Writes a resolved voice_calls row.
    """
    ...
```

**Fallback transcripts** live in `data/fallback_transcripts/`:
- `detention.json` — the hero transcript (matches API Models §7.2's golden example).
- `proactive_checkin.json` — Miguel's Spanish check-in (hos_near_cap variant).

Each is a list of `TranscriptTurn` objects with timestamps relative to call start. `scripts/serve_fallback.py` replays them turn-by-turn with `asyncio.sleep()` matching real inter-turn pacing.

**Detection:** if `place_outbound_call` throws, if the Twilio status callback doesn't arrive within 10s, or if the ElevenLabs post-call doesn't arrive within 2 minutes — safe-mode fires the corresponding gap-fill path.

**Gate** (per `Backend_phase_guide.md` Block 3): with `TWILIO_AUTH_TOKEN` revoked + `RELAY_DEMO_SAFE_MODE=true`, `scripts/rehearse_hero.py` still exits 0.

---

## 10. Observability

- **Every webhook handler logs** `event=webhook provider=twilio|elevenlabs kind=voice|transcript|personalization|post_call call_id=... sid=... verified=true|false latency_ms=...`.
- **Every tool handler logs** `event=tool_call tool=<name> call_id=<uuid> latency_ms=<n> ok=true|false`.
- **Every outbound call placement logs** `event=call_initiated call_id=... twilio_sid=... agent_id=... purpose=...`.
- **Pusher Debug Console** open on a second monitor during the demo — the six WS events per hero flow are the visible heartbeat.
- **Correlation IDs** flow: FE request → BE middleware mints `request_id` → passed as Twilio `statusCallback` query param → echoed back → passed as ElevenLabs dynamic var → echoed back in tool calls and post-call. One grep per call.
- **`/health`** returns `{"status": "ok", "twilio": bool, "elevenlabs": bool, "pusher": bool, "db": bool, "adapter": "navpro|mock|samsara"}`. 503 if any primary dep is down. Fly healthcheck reads this.

---

## 11. Common failure modes + mitigations

| Failure | Symptom | Mitigation |
|---|---|---|
| Twilio signature verification fails on every request | 403 on every webhook | On Fly.io: check `X-Forwarded-Proto` handling; normalize URL scheme to `https`. Also verify `TWILIO_AUTH_TOKEN` matches the account the phone number belongs to. |
| ElevenLabs silently ignores `first_message` override | Agent opens in English despite Spanish first_message | Toggle **Security tab overrides** for that specific agent on the ElevenLabs dashboard. All three toggles (dynamic_variables, first_message, language). |
| Post-call webhook HMAC verification fails intermittently | Some calls process, others 403 | Request body re-read between parse and verify. Read raw bytes **once** via `await request.body()`, hold them, verify, then parse from the cached bytes. |
| ElevenLabs tool call times out mid-conversation | Agent says "Our systems are slow, please hold." then recovers or hangs | Tool endpoint p95 over budget. Check DB index health. Add pre-warm on startup. `ab -n 100 -c 10` to verify p95 < 300ms. |
| Twilio call connects but no media flows | Silent call, no transcript | ElevenLabs agent's phone-number assignment missing or pointing at the wrong agent ID. Verify in the ElevenLabs dashboard Phone Numbers tab. |
| Twilio status callback doesn't arrive | Dashboard stuck in "connected" | 2-minute timeout in the orchestrator; backfill minimal call row from SDK poll of `twilio.rest.Client.calls(sid).fetch()`, publish `call.ended`. |
| Post-call webhook never arrives | Call ends but no transcript in DB | Same — backfill from Twilio side + Pusher `call.ended` with empty transcript. Rare; implies ElevenLabs infra hiccup. |
| ngrok URL changes between dev and demo | Twilio 404 on webhook | Deploy to Fly before rehearsals. All webhooks point at the stable Fly URL. Ngrok is local-dev only. |
| Voicemail picks up instead of a human | `AnsweredBy=machine_start` in Twilio callback | `machine_detection='DetectMessageEnd'` on `calls.create`. Agent keeps talking; we flag the call for voicemail-path post-processing (shorter reschedule, no invoice on detention voicemails). |
| `ELEVENLABS_SERVICE_TOKEN` accidentally rotated | All personalization / transcript webhooks 403 | Rotate both sides (env + ElevenLabs dashboard Webhook tab) at the same time. Never mid-rehearsal. |

---

## 12. Checklist (Block-by-block)

### Block 0 — Foundations
- [ ] Both Twilio numbers purchased; SID + token in `.env`.
- [ ] All three ElevenLabs agents created (`detention_agent`, `driver_agent`, `broker_update_agent`); IDs in `.env`. `driver_ivr_agent` intentionally not created.
- [ ] `ELEVENLABS_SERVICE_TOKEN` + `ELEVENLABS_WEBHOOK_SECRET` generated + stored. Never rotate during demo week.
- [ ] ElevenLabs native Twilio integration: account connected; `TWILIO_FROM_NUMBER` assigned to all three outbound agents.
- [ ] Voice preset "Maya" confirmed on each agent (same voice id across all three).
- [ ] Flash v2.5 selected on each agent (not Flash v2 or Turbo).

### Block 1 — Hello-world outbound
- [ ] Minimal `routes/twilio.py::voice` returns TwiML `<Connect><Stream>` to detention agent.
- [ ] `services/call_orchestrator.place_outbound_call()` wired; calls `twilio.rest.Client.calls.create()`.
- [ ] Single curl command triggers a real outbound call to a teammate's phone; agent audibly speaks its opening line.
- [ ] `/webhooks/twilio/voice/` signature verification green via Twilio's `RequestValidator`.

### Block 2 — Hero flow
- [ ] Detention agent's 3 tools attached (`get_load_details`, `compute_detention_charge`, `log_conversation_outcome`) with the correct webhook URL + `X-Service-Token` in the ElevenLabs Tools tab.
- [ ] **Security tab overrides enabled on detention agent** — all three toggles. Verify by sending a Spanish `first_message` in a test call.
- [ ] Data Collection (4 items) + Evaluation Criteria (`invoice_path_unblocked`) configured on detention agent.
- [ ] Personalization webhook returns dynamic vars for outbound detention; tested via a dummy POST with known `call_id`.
- [ ] Transcript webhook publishes `call.transcript` live on Pusher; partials shimmer on FE.
- [ ] Post-call webhook verifies HMAC + replay; idempotent on `conversation_id`.
- [ ] `pytest backend/tests/test_signatures.py` green.
- [ ] `scripts/rehearse_hero.py` runs end-to-end against live Twilio + ElevenLabs; exits 0.

### Block 3 — Invoice + safe-mode
- [ ] `services/detention.generate_invoice()` formula: half-hour rounding UP, `billable_hours * rate_per_hour`. Verified against golden `$187.50`.
- [ ] Post-call handler triggers invoice on `receiver_accepted_detention == true` OR `ap_email != null`.
- [ ] `data/fallback_transcripts/detention.json` authored; `scripts/serve_fallback.py` replays it turn-by-turn.
- [ ] `RELAY_DEMO_SAFE_MODE=true` path tested with `TWILIO_AUTH_TOKEN` revoked; `scripts/rehearse_hero.py` still exits 0.

### Block 4 — Check-in + anomaly
- [ ] `driver_agent`'s 5 tools attached.
- [ ] **Security tab overrides enabled on `driver_agent`.**
- [ ] Data Collection (7 items) + Evaluation Criteria (`fatigue_captured`, `hos_safety_respected`) configured.
- [ ] Personalization webhook branches on `trigger_reason`; injects `parking_nearby_json` for `hos_near_cap`.
- [ ] `exceptions_engine` publishes `exception.raised` + POSTs `/actions/driver-checkin/` on `missed_checkin`, `hos_near_cap`, `eta_drift`, `extended_idle`.
- [ ] 90-min cooldown (scheduled) + driving gate (non-`hos_near_cap`) enforced in `routes/actions.py::driver_checkin`.
- [ ] Post-call unpacks `data_collection_results` onto Driver; publishes `load.updated`.
- [ ] `pytest backend/tests/test_proactive_checkin.py` green.

### Block 4.5 — Broker update agent (lightweight, runs alongside Block 4)
- [ ] `broker_update_agent`'s 3 tools attached (`get_load_details`, `get_driver_status`, `log_conversation_outcome`).
- [ ] **Security tab overrides enabled on `broker_update_agent`.**
- [ ] Data Collection (3 items) + Evaluation Criteria (`broker_informed`) configured.
- [ ] `routes/actions.py::batch_broker_updates` fans out via `asyncio.Semaphore(settings.batch_calls_max_concurrency)` (default 8; drop to 5 if ElevenLabs concurrency errors).
- [ ] One manual end-of-day batch POST against 2 seeded brokers → both calls place, both post-call webhooks arrive, `load.updated` fires twice.

### Block 5 — Polish
- [ ] Tighten each agent's opening line; record 10 samples per agent, pick best.
- [ ] Confirm Flash v2.5 on both active agents.
- [ ] Record fallback MP4 for detention call (judge-grade audio).

### Block 6 — Ship
- [ ] Twilio voice webhook pinned to Fly URL (not ngrok).
- [ ] All three ElevenLabs agent webhook URLs pinned to Fly URL (personalization, transcript, post-call).
- [ ] `/health` returns all green on Fly.
- [ ] `scripts/rehearse_hero.py` against Fly URL exits 0.

### Block 7 — Dry runs
- [ ] Revoke Twilio auth token mid-call → safe-mode takes over in <1s → dashboard identical → reinstate token.
- [ ] Run hero flow 5× consecutively without restarting anything.
- [ ] Rotate `ELEVENLABS_SERVICE_TOKEN` in env + dashboard simultaneously; verify subsequent calls still work (sanity check on the rotation process).

---

## 13. Cross-cutting rules

- **No SIP / custom VoIP.** Always use ElevenLabs native Twilio integration.
- **No browser-side voice code.** FE never touches Twilio.js or ElevenLabs SDK directly.
- **No background call polling.** Everything is webhook-driven + idempotent. Polling Twilio is a last-resort backfill for missed status callbacks.
- **No unauthenticated webhook handlers.** Every inbound webhook verifies signature / token before reading body.
- **One agent per persona.** Do not mix detention + check-in into one agent even though tool sets overlap; prompts and Evaluation Criteria are different.
- **Never silently rotate secrets during demo week.** `TWILIO_AUTH_TOKEN` + `ELEVENLABS_*` locked Friday evening through Sunday submission.
- **Never ship a new tool without adding it to API Models §6.** Ever.
- **All changes to webhook URLs, agent IDs, or voice preset trigger a rehearsal rerun.** Non-negotiable.

---

## 14. Open questions

1. **ElevenLabs `post_call_audio` delivery latency.** Ours is usually <30s; sometimes >2min. FE does not wait for it — `audio_url` on `/calls/[id]` is `null` initially and hydrates on a later visit. Doesn't block the demo; noted for Q&A.
2. **Machine detection true-negative rate.** `DetectMessageEnd` is accurate enough for the demo but can occasionally flag a human as machine if they speak too slowly. If it bites us in rehearsal, switch to `Enable` (less aggressive) and accept longer leave-a-message on voicemails.
3. **ElevenLabs rate limits** — Creator tier caps concurrency at ~5 parallel calls. With `broker_update_agent` re-activated, `batch_broker_updates` is exposed to this cap again. Default `batch_calls_max_concurrency = 8` — **drop to `5` if any 429s appear during rehearsal** and re-test. Solo detention / driver check-in flows stay well under the cap.
4. **Punjabi voice preset** — not provisioned. Deferred by Build Plan ruthless-cut order. If added later, confirm Maya voice exists in `pa`; ElevenLabs library coverage varies.

---

**The phone call is the product. The webhook verification is what makes it safe. Get both right; everything else is plumbing.**
