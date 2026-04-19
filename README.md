<div align="center">

# Relay

### Outbound voice agent for small-fleet dispatchers

**[🚀 Live demo → relay-trucker.netlify.app](https://relay-trucker.netlify.app)**

*Globe Hacks 2026 · Trucker Path track · ElevenLabs dual submission*

[![Backend](https://img.shields.io/badge/backend-FastAPI-009485?style=flat-square)](https://relay-truckerpath-b1b6f88e3d10.herokuapp.com/health)
[![Frontend](https://img.shields.io/badge/frontend-Next.js_14-000000?style=flat-square)](https://relay-trucker.netlify.app)
[![Voice](https://img.shields.io/badge/voice-ElevenLabs_ConvAI-FF6B35?style=flat-square)](https://elevenlabs.io/conversational-ai)
[![LLM](https://img.shields.io/badge/reasoning-Claude_Sonnet_4.6-CC785C?style=flat-square)](https://anthropic.com)
[![DB](https://img.shields.io/badge/db-Supabase-3ECF8E?style=flat-square)](https://supabase.com)
[![Telephony](https://img.shields.io/badge/telephony-Twilio-F22F46?style=flat-square)](https://twilio.com)

</div>

---

## What is Relay

Small-fleet dispatchers (5–50 trucks) burn **2-3 hours a day on the phone** chasing brokers for check-calls, fighting receivers over detention, coordinating HOS, and texting drivers who won't pick up. They lose roughly **$52k/year per dispatcher in labor** and another **~$45k/year per 8-truck fleet** in uncollected detention charges nobody has time to dispute.

Every "AI dispatcher copilot" on the market is **inbound-only** — the dispatcher has to open an app, type, and wait. Relay is the opposite: **it makes the calls on the dispatcher's behalf**, triggered by Trucker Path's own driver-side data, in Spanish / English / Punjabi, and logs a dispute-ready transcript every single time.

> *The dispatcher never picks up a phone. The call gets made anyway.*

---

## What it does — the four-workflow loop

```
  ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
  │  DETECT  │─────▶│  TRIGGER │─────▶│   CALL   │─────▶│   LOG    │
  └──────────┘      └──────────┘      └──────────┘      └──────────┘
   NavPro +          Rule + Claude     ElevenLabs +      Transcript +
   HOS tick          reasoning layer   Twilio outbound   invoice PDF
```

**One ingest pipeline. Four voice agents. One dispatcher dashboard.**

| # | Workflow | Agent speaks to | Triggered by |
|---|---|---|---|
| 1 | **Consignment assignment** | Dispatcher UI (Claude-written recommendation) | New unassigned load lands |
| 2 | **Proactive driver check-in** | Driver | HOS near cap · ETA drift · extended idle · scheduled |
| 3 | **Detention escalation** | Receiver AP / supervisor | Truck sits past free-wait window at a stop |
| 4 | **Broker check-call batch** | Broker dispatch | End-of-day / pre-delivery cadence |

Plus: **inbound driver IVR** for when the driver calls *Relay* (multilingual, structured data collection back into the dashboard).

---

## Features

### 🚛 Fleet intelligence
- **Live fleet map** — every truck's GPS, HOS clock, fatigue level, active load
- **Consignment scorer** — ranks drivers for unassigned loads by HOS headroom / proximity / freshness / fatigue (35/35/15/15 weights); Claude Sonnet 4.6 writes the one-paragraph "why #1" the dispatcher reads aloud
- **Real-time detention tracking** — live clock, projected dollar amount, whether a call has been made, linked invoice status
- **Per-driver timeline** — chronological feed of check-ins, voice calls, load assignments

### 📞 Voice agents (ElevenLabs ConvAI 2.0, Flash v2.5, <75ms latency)
- **4 persona-distinct agents** — warm driver check-in, assertive detention, brisk broker updates, patient multilingual IVR
- **Real tool use mid-call** — agents call our backend for load details, HOS, detention math, parking lookup, incident logging
- **Multilingual day one** — English / Spanish / Punjabi with mid-conversation switching
- **Full analysis per call** — transcript, 6 evaluation criteria (goal met, safety respected, call ended appropriately…), 14 structured data fields (fatigue, HOS self-report, ETA confidence, vehicle issues, parking needs…)

### 💰 Billing + POD
- **Auto-generated detention invoices** on `committed_to_pay=true` — math driven by the live transcript
- **One-click invoice send** with destination email audit trail
- **POD capture** per load with signed-by + timestamp, auto-flips load to `delivered`

### 🧠 Claude Sonnet 4.6 reasoning layer
- **Anomaly agent** at the Relay↔NavPro seam — decides whether to fire a proactive call when hard rules don't cover the case (silence + tracking staleness + soft signal combo)
- **Consignment agent** — writes the dispatcher-facing recommendation paragraph over the deterministic scorer's ranking
- **Forced tool use + ephemeral prompt caching + 3s hard timeout** → always safe to fall back to a deterministic default, never blocks a user

### 🔒 Safety + compliance
- **Never call a driving truck** (FMCSA §392.82 handheld ban) — scheduler waits for rest/on-duty-not-driving windows; only event-level `hos_near_cap` bypasses
- **90-min cooldown** between scheduled check-ins per driver
- **90-second call cap** when fatigue is high — we never eat a tired driver's rest window
- **HMAC-verified webhooks**, Bearer-token-gated tool endpoints, constant-time compare on every auth path

---

## How it works

### Architecture

```
┌─────────────────────────────┐          ┌──────────────────────────┐
│  Next.js 14 dashboard       │ ◀──REST──▶│  FastAPI backend         │
│  relay-trucker.netlify.app  │          │  (Heroku)                │
│                             │          │                          │
│  /dashboard                 │          │  /dispatcher/*   reads   │
│  /dashboard/assign          │          │  /tools/*        agent   │
│  /dashboard/calls           │          │  /internal/*     actions │
│  /dashboard/billing         │          │  /webhooks/*     ingest  │
│  /dashboard/drivers         │          └────┬─────────────┬───────┘
└─────────────────────────────┘               │             │
                                              ▼             ▼
                         ┌──────────────────────┐   ┌──────────────┐
                         │ Supabase Postgres    │   │ ElevenLabs   │
                         │ (14 tables,          │   │ ConvAI 2.0   │
                         │  4 migrations)       │   │ + Twilio     │
                         └──────────────────────┘   └──────────────┘
                                              ▲
                                              │
                         ┌──────────────────────┐
                         │ NavProAdapter        │   ← Trucker Path partner API
                         │ (live fleet data)    │      (pull-only, 25 QPS)
                         └──────────────────────┘
                                              ▲
                                              │
                         ┌──────────────────────┐
                         │ Claude Sonnet 4.6    │   ← anomaly + consignment
                         │ (reasoning layer)    │      agents (forced tool use)
                         └──────────────────────┘
```

### The call lifecycle

```
① Anomaly agent (Claude) or dispatcher click fires:
     POST /internal/call/initiate { agent_kind, driver_id?, load_id? }
         ↓
② Backend inserts voice_calls row (call_status='dialing')
     and POSTs to ElevenLabs /v1/convai/twilio/outbound-call
         ↓
③ ElevenLabs + Twilio dial the phone. Agent speaks using
     the prompt configured in the ElevenLabs dashboard.
         ↓
④ During the call, the agent hits our tool endpoints:
     GET   /tools/driver/context
     GET   /tools/load/rate_con_terms
     POST  /tools/detention/confirm
     GET   /tools/parking/nearby
     POST  /tools/dispatcher/notify     ← 14 tools live
         ↓
⑤ Call ends → ElevenLabs fires HMAC-signed post_call webhook:
     POST /webhooks/elevenlabs/post_call
         ↓
⑥ Backend verifies HMAC, UPSERTs voice_calls, branches on agent_id:
     • detention_agent + committed_to_pay → generate invoice (background)
     • driver_agent    + issues_flagged   → urgent dispatcher task
     • broker_update_agent                → just updates last_broker_update_at
         ↓
⑦ Supabase row write → Realtime subscription → dashboard updates instantly.
     /dashboard/calls renders the full transcript, evaluation criteria,
     and 14 data collection fields inside a 4-tab detail modal.
```

### Deterministic scorer (consignment)

Every unassigned load runs through a transparent linear scoring function. No black box, no ML model — the dispatcher can explain exactly why Tommy beat Carlos on any load:

```
score = 35% · hos_headroom_normalized
      + 35% · proximity_normalized     (haversine to pickup)
      + 15% · freshness                (hours since last_assigned_at)
      + 15% · fatigue_penalty          (low=1.0, high=0.0)

Hard filters applied first:
  status ∈ {driving, off_duty, sleeper}       → disqualified
  hos_drive < deadhead + 2h buffer             → insufficient_hos
  no GPS fix                                   → no_gps_fix
```

Claude only runs *after* the scorer — its job is to write a 2-3 sentence explanation ("Tommy is already at Phoenix DC with 9 hours of drive time left — he can grab this load without any deadhead…"), never to override the scorer's math.

---

## Tech stack

| Layer | Tech | Why |
|---|---|---|
| **Frontend** | Next.js 14 App Router · TypeScript · Tailwind · shadcn/ui | Production-grade UI in hackathon time |
| **Frontend hosting** | Netlify | Zero-config edge deploy |
| **Backend** | FastAPI · Python 3.11 · Uvicorn · SQLAlchemy 2.x async · Pydantic Settings | Async Python, typed config, clean dep injection |
| **Backend hosting** | Heroku (Basic dyno) | Single-command git deploys |
| **Voice agent** | ElevenLabs ConvAI 2.0 · Flash v2.5 · forced tool use | <75ms latency, 4-persona voice design |
| **Telephony** | Twilio (native ElevenLabs integration) | Outbound + inbound US numbers |
| **Reasoning** | Claude Sonnet 4.6 · forced tool use · ephemeral prompt caching | Safe tool-only output shape, 80%+ cache hit on system prompt |
| **Database** | Supabase Postgres · Alembic migrations · asyncpg pooler | Realtime subscriptions to tables replace WebSocket middleware |
| **Fleet data** | NavPro partner API · pull-only · 25 QPS soft cap | Real GPS + trip data, no HOS |
| **Testing** | 4 end-to-end stress scripts | Hero detention · consignment · dashboard · full endpoint suite |

### Responsible-AI + cost controls

- **3-second hard client timeout** on every Claude call → agents never block user flow
- **Deterministic fallback** on every Claude path → works with `ANTHROPIC_API_KEY=""`
- **Ephemeral prompt caching** on system prompts → ~80% input-token discount at scheduler cadence
- **Kill switches**: `ANOMALY_AGENT_ENABLED=false`, `ANTHROPIC_API_KEY=""`, `ELEVENLABS_API_KEY=""` each disable one cost layer without breaking the rest

---

## Repo layout

```
relay/
├── frontend/                        # Next.js dispatcher dashboard
│   ├── app/dashboard/
│   │   ├── assign/                  # 9am "Who gets this Dallas load?" — consignment scorer + Claude
│   │   ├── active/                  # live map + fleet feed
│   │   ├── calls/                   # all ElevenLabs calls · 4-tab detail · escalation hotline
│   │   ├── billing/                 # invoice list · send · POD
│   │   └── drivers/                 # per-driver detail + timeline
│   ├── components/dashboard/        # NavSidebar, DetailPanel, TranscriptFeed
│   ├── lib/api.ts                   # typed envelope-unwrapping HTTP client
│   └── shared/types.ts              # canonical types (mirrors backend/models/schemas.py)
│
├── backend/
│   ├── main.py                      # FastAPI factory + lifespan (scheduler task)
│   ├── config.py                    # Pydantic Settings (env var truth)
│   ├── routes/
│   │   ├── tools.py                 # 14 ElevenLabs agent tool endpoints
│   │   ├── webhooks_elevenlabs.py   # post_call (HMAC) + personalization
│   │   ├── internal.py              # invoice generation, urgent queue, manual scheduler tick
│   │   ├── calls.py                 # /internal/call/initiate — outbound orchestrator
│   │   ├── consignment.py           # /dispatcher/loads/unassigned, candidates, assign
│   │   └── dashboard.py             # /dispatcher/fleet/live, detentions, invoices, calls
│   ├── services/
│   │   ├── anomaly_agent.py         # Claude Sonnet 4.6 scheduler-side reasoning
│   │   ├── consignment.py           # deterministic load-driver scorer
│   │   ├── consignment_agent.py     # Claude recommendation layer
│   │   ├── call_orchestrator.py     # per-agent phone_number_id routing
│   │   ├── detention.py             # invoice math + row insert
│   │   ├── checkin_scheduler.py     # tiered cron (12h cadence, manual tick endpoint)
│   │   ├── exceptions_engine.py     # hard-rule evaluator (HOS, idle, tracking staleness)
│   │   ├── signatures.py            # HMAC-SHA256 verify
│   │   └── adapters/                # NavProAdapter (live) + MockTPAdapter (Wi-Fi fallback)
│   ├── models/db.py                 # 14 SQLAlchemy tables, all PKs TEXT
│   ├── db/migrations/versions/      # 4 alembic migrations
│   ├── prompts/                     # anomaly_agent + consignment_agent system prompts
│   └── scripts/                     # stress_* end-to-end smokes
│
├── data/                            # seed JSON (drivers · loads · brokers · parking POI · repair shops)
├── API_DOCS/                        # PMD, tools contract, changelog
└── README.md                        # you are here
```

---

## Run locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # fill in secrets
alembic upgrade head
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                          # → http://localhost:3000
```

---

## Differentiator

Every prior hackathon project in logistics stops at a chat UI or a dashboard with recommendations.

**Relay makes the call.** The dispatcher never picks up a phone. And the call is triggered by Trucker Path's own data — a moat no other voice vendor can replicate without rebuilding Trucker Path itself.

---

## Canonical docs

| Doc | Lives in |
|---|---|
| PMD · Pitch · API Models · Build Plan | [Notion workspace](https://www.notion.so/347dab51d63481829ea2fe7cef1b0009) |
| API shapes + tool contract | [`API_DOCS/tools_contract.md`](./API_DOCS/tools_contract.md) |
| Backend engineering contract | [`backend/CLAUDE.md`](./backend/CLAUDE.md) |
| NavPro integration guide | [`API_DOCS/NavPro_integration.md`](./API_DOCS/NavPro_integration.md) |
| ElevenLabs + Twilio setup | [`API_DOCS/ElevenLabs_Twilio_integration.md`](./API_DOCS/ElevenLabs_Twilio_integration.md) |

---

<div align="center">

**[Live demo](https://relay-trucker.netlify.app) · [Backend health](https://relay-truckerpath-b1b6f88e3d10.herokuapp.com/health)**

Built for Globe Hacks 2026.

</div>
