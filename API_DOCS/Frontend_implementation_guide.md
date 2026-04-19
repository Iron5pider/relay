# Relay Frontend — Phased Implementation Guide

> **Mirror doc to `Backend_phase_guide.md`.** Same block numbering, same gate-based cadence. Everything here is the FE-specific checklist that the Notion **Build Plan** leaves implicit, scoped to the **Build Scope** 3-feature P0 lock.
>
> **Precedence:** Notion **API Models** (canonical contracts) · Notion **Build Scope** (P0 prioritization) · Notion **Build Plan** (sequence) · `backend/models/CLAUDE.md` (BE contract — FE reads it to understand WS payloads & endpoint shapes) · this doc. On any conflict, the Notion pages win.
>
> **FE session operating contract.** This doc **is** the FE session's operating contract (there is no separate `frontend/CLAUDE.md`). Read `API_DOCS/build_scope.md` before every edit, read the last 5 changelog entries, then consult this guide for the block's checklist.

## 0. Ground rules (non-negotiable)

1. **Types come from the Notion API Models page.** `frontend/shared/types.ts` mirrors API Models §3 field-for-field. Same casing (`snake_case`), same enum string values, same nullability. A FE↔BE schema drift is the #1 way the demo breaks. When you need a type, check `types.ts` first; if it's not there, add it from the Notion page in the same PR as the backend mirror.
2. **Never invent a WebSocket event.** The six events in API Models §5 are fixed: `load.updated`, `exception.raised`, `call.started`, `call.transcript`, `call.ended`, `invoice.generated`. If you think you need a new one, you don't — reshape the payload of an existing one (e.g. fatigue updates piggyback on `load.updated`).
3. **Never call Twilio or ElevenLabs from the browser.** All voice plumbing goes through the FastAPI backend. The dashboard POSTs to `/api/v1/actions/*`, subscribes to the WS channel, and renders. Everything else is BE.
4. **Publish after DB commit, not before — is a backend rule, but** its corollary on the FE is: treat every WS event as additive and idempotent. Render what arrived; reconcile from `GET /api/v1/loads/` on mount/reconnect. Never assume event ordering.
5. **The hero beat is Beat 2 (detention → invoice).** Every FE decision flows from: will a judge watching for 30 seconds understand what just happened? If the answer is "probably not," cut the UI element or simplify.
6. **Demo is the product.** Empty states, loading states, error states that a judge will see must be styled. Error states the judge will never see can log and move on.
7. **PDF rendering lives on the frontend.** `@react-pdf/renderer` runs in a Next.js route handler. FastAPI **never** renders PDFs.

## 1. Tech stack (locked)

| Layer | Choice | Notes |
|---|---|---|
| Framework | Next.js 14 App Router + TypeScript | `create-next-app` with App Router, not Pages Router |
| Styling | Tailwind CSS + shadcn/ui | Trucker Path accent + neutral grayscale + single alert red |
| Realtime client | Pusher JS (`pusher-js`) | Matches BE's `pusher` Python lib; swap to Ably only if BE swaps first |
| PDF | `@react-pdf/renderer` | Server-rendered in a Next.js route handler |
| Data fetching | Native `fetch` in server components; SWR for client polling of non-live reads | No tRPC, no RSC experiments — it's 36 hours |
| State (client) | React state + `useSyncExternalStore` for the WS bus | No Redux, no Zustand, no Jotai — do not install |
| Hosting | Vercel | Connected to the GitHub repo, auto-deploy on push to main |
| Icons | `lucide-react` | Ships with shadcn |
| Dates | `date-fns` (only where needed) | No moment, no dayjs |

**Nothing else gets installed without a changelog justification.** Speculative libraries are a drift risk — if you can't justify it in one sentence in the changelog, don't install it.

## 2. Project structure (inside `frontend/`)

```
frontend/
├── app/
│   ├── layout.tsx                    # root: Tailwind, Pusher provider, font
│   ├── page.tsx                      # Dispatcher dashboard (HOME — the demo screen)
│   ├── calls/[callId]/page.tsx       # Full transcript + audio playback + outcome
│   ├── invoices/[invoiceId]/page.tsx # Embedded PDF viewer
│   ├── invoices/[invoiceId]/pdf/     # Next.js route handler → @react-pdf/renderer stream
│   │   └── route.ts
│   ├── drivers/page.tsx              # Driver roster w/ HOS + last check-in (reads from BE)
│   ├── brokers/page.tsx              # Broker book (light; nice-to-have)
│   └── demo/page.tsx                 # Presenter control room (three big buttons)
│
├── components/
│   ├── LoadTable.tsx                 # Main dashboard table, live ticks
│   ├── LoadRow.tsx                   # Row with status badge + anomaly pulse + detention timer
│   ├── ExceptionBadge.tsx            # Red pulsing badge for exception_flags
│   ├── AnomalyBadge.tsx              # Same visual family, fires on exception.raised
│   ├── DriverCheckinCard.tsx         # Fatigue chip, 3-clock HOS mini, ETA confidence, last check-in
│   ├── TranscriptPanel.tsx           # Live streaming transcript (typewriter reveal)
│   ├── CallStatusBanner.tsx          # "Calling receiver…" / "Connected" / "Completed"
│   ├── CallWaveform.tsx              # Minimal canvas waveform (P1.5 polish)
│   ├── InvoicePDF.tsx                # @react-pdf/renderer document component
│   ├── InvoiceModal.tsx              # Auto-opens on invoice.generated
│   ├── TriggerButton.tsx             # "Escalate", "Check in with Miguel", "Play fallback"
│   └── ui/                           # shadcn-generated primitives
│
├── lib/
│   ├── api.ts                        # Typed fetch wrappers, one per endpoint from shared/
│   ├── realtime.ts                   # Pusher client singleton + useChannel hook
│   ├── demo-flags.ts                 # NEXT_PUBLIC_* runtime flags
│   └── time.ts                       # formatDetentionTimer, formatHos
│
├── shared/                           # SINGLE SOURCE OF TRUTH — mirrors backend/models/schemas.py
│   ├── types.ts                      # All TypeScript types from API Models §3
│   └── endpoints.ts                  # Path + method + req/resp type tuples
│
├── public/
│   ├── logo.svg                      # Acme Trucking mark (demo brand)
│   └── fallback_audio/               # MP3 copies for the /demo page player (served statically)
│
├── tailwind.config.ts
├── next.config.mjs
├── tsconfig.json
├── package.json
└── .env.local.example                # NEXT_PUBLIC_* only; API secrets live in .env (BE)
```

## 3. Shared types — parity rules

`frontend/shared/types.ts` mirrors `backend/models/schemas.py` **field-for-field**. Non-negotiable:

- **Casing:** `snake_case` on the wire. **Do not** camelCase at the boundary. Accept `camelCase` inside components if a reviewer insists, but only after `lib/api.ts` has converted — never at the network layer. Safer default: leave it `snake_case` everywhere.
- **Enums:** string unions matching the backend's `str`-Enum values exactly. `'detention_escalation'`, never `'DETENTION_ESCALATION'` or `'detentionEscalation'`.
- **Nullability:** Python `Optional[T] = None` ↔ TS `T | null`. Treat missing keys as null defensively, but the BE promises to return `null` for known-absent values (API Models §1).
- **Money:** backend Pydantic serializes as `number`. Use plain `number` in TS; format to 2 decimals at render time. Never add/multiply money in the browser — the backend already computed it.
- **F6b + Build Scope (2026-04-19) additions** that must exist in `types.ts`:
  - `FatigueLevel`, `EtaConfidence`, `CheckinTriggerReason` (incl. **`missed_checkin`** from the Build Scope Feature 2 lock).
  - `CallPurpose` includes `driver_proactive_checkin` (outbound) alongside `driver_checkin` (inbound — documented but unused per Build Scope).
  - `Driver` gains `fatigue_level`, `last_checkin_at`, `next_scheduled_checkin_at`.

**Schema-drift check script** (Dev B owns): add `scripts/check_schema_parity.ts` that `fetch`es the backend's `/api/v1/loads/` golden response, validates shape against `types.ts`, and fails CI on mismatch. Low effort, huge payoff. Run before every push that touches either side of the type boundary.

## 4. Environment & secrets

The frontend only sees `NEXT_PUBLIC_*` vars. Everything else lives in `.env` on the backend (Fly.io). Mirror this `.env.local.example`:

```bash
# .env.local.example
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000     # Fly URL in prod
NEXT_PUBLIC_PUSHER_KEY=
NEXT_PUBLIC_PUSHER_CLUSTER=us3
NEXT_PUBLIC_DISPATCHER_ID=demo                     # single dispatcher for hackathon
```

`NEXT_PUBLIC_DISPATCHER_ID` gates the channel name: `dispatcher.${NEXT_PUBLIC_DISPATCHER_ID}` → `dispatcher.demo` in the hackathon. Production would inject this from SSO.

**Auth.** Every BE request sends `X-Relay-Dispatcher-Id: demo` (API Models §1). `lib/api.ts` injects it automatically. Don't sprinkle it on individual calls.

## 5. Block-by-block checklist

### Block 0 — Foundations (Pair)

Backend owns Twilio / ElevenLabs / Postgres / Pusher sponsor tasks. FE side of Block 0:

- [ ] `create-next-app` initialized in `frontend/` with TypeScript, App Router, Tailwind, ESLint.
- [ ] shadcn/ui bootstrapped (`npx shadcn-ui@latest init`); install `button`, `table`, `badge`, `card`, `dialog`, `skeleton`, `toast`.
- [ ] Vercel project linked to repo. `NEXT_PUBLIC_*` env vars populated in Vercel dashboard as they land.
- [ ] Brand lock: primary color (Trucker Path accent blue), alert red (`rgb(220 38 38)` — Tailwind `red-600`), neutral grayscale. Font: Inter. Logo placeholder in `public/logo.svg`.
- [ ] `NEXT_PUBLIC_DISPATCHER_ID=demo` agreed with BE; corresponding channel in BE is `dispatcher.demo`.

**Gate:** `pnpm dev` renders the Next.js welcome screen; Vercel preview deploys from main push.

### Block 1 — Hello-world dashboard + shared types (Dev B)

**Goal:** Seed data rendered in a table. Shared types locked. No interactivity yet. *(Build Plan Block 1 Dev B scope.)*

- [ ] `frontend/shared/types.ts` — copy from the Notion API Models §3 block **verbatim**. Sync with `backend/models/schemas.py` in the same PR. Include F6b additions AND `missed_checkin` per Build Scope.
- [ ] `frontend/shared/endpoints.ts` — path + method + req/resp tuples for every endpoint in `build_scope.md` §4. Typed fetch wrappers in `lib/api.ts` use these.
- [ ] `lib/api.ts` — typed wrappers. One function per endpoint: `listLoads`, `getLoad`, `getCall`, `listCalls`, `getInvoice`, `escalateDetention`, `batchBrokerUpdates` (for completeness, even though broker batch is deferred — wrap but don't wire a button), `driverCheckin`. Inject `X-Relay-Dispatcher-Id` header.
- [ ] `lib/realtime.ts` — Pusher singleton, `useChannel(channelName)` hook. `useChannel` returns a subscription + emits into a Zustand-free custom store via `useSyncExternalStore`.
- [ ] `app/page.tsx` — server-fetch from `/api/v1/loads/`; render `LoadTable` with all 8 seed loads. Exception rows get red left border + `ExceptionBadge`. Detention timer on the row updates client-side using `arrived_at_stop_at` + `Date.now()` (no WS needed for the second-by-second tick).
- [ ] `components/LoadRow.tsx`, `components/LoadTable.tsx`, `components/ExceptionBadge.tsx` built with shadcn `Table` + `Badge`.
- [ ] Static styling: Tailwind utility classes only. No CSS files yet (except `globals.css`).
- [ ] **Schema parity check** passes against a running BE (seed-loaded DB).

**Gate (Build Plan):**
- [ ] Dashboard renders all 8 seed loads in a styled table.
- [ ] Exception row (L-12345) is visually distinct — a stranger would notice within 3 seconds.
- [ ] `shared/types.ts` and `backend/models/schemas.py` diff-check clean.

### Block 1.5 — Pusher bus wiring (Dev B, parallel to BE's adapter work)

**Goal:** Prove the WS client side-by-side with BE's publisher, even though no real events flow yet. *(Not in Build Plan — insert explicitly.)*

- [ ] Pusher client subscribes to `dispatcher.demo` on mount in `app/layout.tsx`.
- [ ] Custom event store in `lib/realtime.ts` exposes:
  - `useLoads()` — hydrated from initial fetch, patched by `load.updated`.
  - `useCall(callId)` — optional hook for `/calls/[callId]` page.
  - `useLiveTranscript(callId)` — queues all `call.transcript` events (final + partial) for a single call.
  - `useExceptions()` — stream of `exception.raised` for the anomaly feed rail.
  - `useLatestInvoice()` — fires a modal open on `invoice.generated`.
- [ ] Test harness: `scripts/fake-pusher-event.ts` fires a `load.updated` event into the local Pusher app from a Node shell. Dashboard should update live.

**Gate:** a single test event from the script animates a row in the local dashboard within 1 second.

### Block 2 — Hero flow (Pair first, then split) — **Feature 3 of Build Scope**

**Goal:** The detention escalation button on the dashboard fires a real call end-to-end, transcript streams into the panel. Beat 2 of the demo arc. *(Build Plan Block 2.)*

#### Dev B — Dashboard interactivity + transcript panel
- [ ] `TriggerButton.tsx` — one-click "Escalate" on exception rows. POSTs `/api/v1/actions/escalate-detention/` with `{ load_id, auto_invoice: true }`. Optimistic: immediately shows a `CallStatusBanner` in "Calling receiver…" state using the response's `call_id`.
- [ ] `CallStatusBanner.tsx` — tri-state: `calling | connected | completed`. Transitions driven by WS:
  - `call.started` → `connected`
  - `call.ended` → `completed`
- [ ] `TranscriptPanel.tsx` — lives in a right-side rail. Subscribes via `useLiveTranscript(call_id)`.
  - **Publish partial turns, render partial turns** (BE publishes both final and partial; the dashboard shows partials to get the live shimmer).
  - Typewriter reveal per turn at ~30ms per char (synced to audio-ish, not perfect; "feels live").
  - Speaker avatar on the left (Maya = agent = blue; human = gray).
  - Auto-scroll to bottom; pause auto-scroll on user hover over the panel.
- [ ] Expected-detention pill (`$187.50`) surfaces in the banner pulled from `EscalateDetentionResponse.expected_detention_amount`.

#### Dev B — Feature 3 Completion gates
- [ ] Clicking Escalate → BE fires outbound call → phone rings in the room → transcript streams in the panel in real time.
- [ ] Call ends cleanly → CallStatusBanner transitions to `completed`.
- [ ] Invoice modal auto-opens on `invoice.generated` within 3s of call end (see Block 3).
- [ ] Flow works ten consecutive times on venue Wi-Fi (joint gate with BE).

### Block 3 — Invoice PDF + Auto paper trail + Demo-safe-mode UI (Dev B)

**Goal:** Produce the on-screen artifact. Polish the hero. *(Build Plan Block 3.)*

#### Dev B — Invoice PDF via `@react-pdf/renderer`
- [ ] `components/InvoicePDF.tsx` — server-rendered React-PDF document.
  - Header: Acme Trucking letterhead block (logo + address block placeholder).
  - Body: Load # (L-12345), driver, receiver, appointment time, arrival time, minutes-at-stop, rate, billable half-hours, total.
  - **Evidence footer:** 2–3 transcript excerpts from the Call (agent + human alternating). This is what makes it judge-grade.
  - Rate-con reference line at the bottom (hardcoded string — we don't parse rate-cons in scope).
- [ ] `app/invoices/[invoiceId]/pdf/route.ts` — `GET` handler, fetches invoice + call via `/api/v1/invoices/{id}/` and `/api/v1/calls/{call_id}/`, renders PDF stream, returns with `Content-Type: application/pdf`.
- [ ] `components/InvoiceModal.tsx` — dialog that embeds an `<iframe src="/invoices/{id}/pdf">`. Auto-opens on `useLatestInvoice()` firing.
- [ ] Formula sanity: the page displays `detention_minutes`, `billable_hours` (half-hour rounded up), `rate_per_hour`, `amount_usd` — all pulled from the BE response. Never recompute on the FE. For L-12345: 167 min / 2.5h billable / $75/h / **$187.50** (formula locked 2026-04-19; see Backend_phase_guide §"Known spec gaps" #1).

#### Dev B — Demo-safe-mode UX (mirrors BE `RELAY_DEMO_SAFE_MODE`)
- [ ] The dashboard and invoice modal must look **identical** on a safe-mode run. No "synthetic" badges, no toasts saying "mocked," no warning banners. If safe mode fires, the judge sees exactly what a live call produces.
- [ ] One detectable FE tell (for the presenter only, not judges): a tiny monospace `SAFE` chip in the bottom-right corner of `app/demo/page.tsx`, hidden on `/`.
- [ ] `NEXT_PUBLIC_ALLOW_SAFE_MODE_BANNER=false` in prod; the BE `demo_safe_mode` flag is authoritative, the FE just reads what it gets via WS.

#### Dev A — Hero audio polish (voice/BE territory; FE depends on it but doesn't own it)

**Gates (Build Plan, Build Scope Feature 3):**
- [ ] Detention call completion generates + displays the invoice PDF on screen within **3 seconds**.
- [ ] PDF reads as a real document (letterhead, transcript evidence, total).
- [ ] Fallback MP4 captured and playable from `/demo` (see Block 5 — `/demo` page).

### Block 4 — Proactive Check-In + Anomaly Detection (Dev A BE / Dev B FE) — **Features 1 & 2 of Build Scope**

**Goal:** Beat 1 of the demo arc. *(Build Plan Block 4 repurposed per Build Scope; broker batch + inbound IVR deferred.)*

#### Dev B — Driver command center components
- [ ] `components/DriverCheckinCard.tsx` — one card per driver in a side rail or `/drivers` page:
  - Fatigue chip (`low/moderate/high/unknown` → green/amber/red/gray).
  - Three-clock HOS mini (drive / shift / cycle), with a "near cap" amber styling when any clock < 30 min.
  - ETA confidence chip (`on_time/at_risk/late`).
  - Last check-in timestamp, relative ("5m ago", "2h ago").
  - Updates live on `load.updated` — BE publishes this after the post-call writeback stamps the driver row (API Models §5 reuses `load.updated`; do NOT invent a `driver.updated` event).
- [ ] `components/AnomalyBadge.tsx` — pulsing red border on the affected driver row AND a live "Anomalies" rail entry. Fires on `exception.raised` where `event_type in {missed_appointment, hos_warning, late_eta, breakdown}`.
- [ ] **Manual trigger button** on the driver row / card: "Check in with {driver_name}" → POSTs `/api/v1/actions/driver-checkin/` with `trigger_reason: 'manual'`. Same WS lifecycle as detention (`call.started` → `call.transcript` → `call.ended`).
- [ ] On the live call, `TranscriptPanel` can render Spanish turns — language attribute is per-turn (API Models §3 `TranscriptTurn.language`). No translation layer.

#### Dev B — Beat 1 demo arc
- [ ] Miguel's seeded row + `AnomalyBadge` firing auto-triggers the outbound check-in call (BE exceptions_engine owns this; FE just renders).
- [ ] On post-call `load.updated`, the `DriverCheckinCard` chip animates from "unknown" → "moderate" (or whatever the driver said). A 500ms color transition — not a jarring snap.

#### [DEFERRED] Build Scope moves these out of P0
- ~~"Send 3 p.m. Update" batch button~~ — no FE component for broker batch.
- ~~Driver IVR number display on `/demo`~~ — inbound IVR deferred.
- ~~IVR-driven row animation on `record_driver_checkin`~~ — no inbound path.

Keep `lib/api.ts::batchBrokerUpdates` as a stub — no button wires to it. If a judge asks "where's the batch?" the answer is "it's implemented server-side, we chose to scope the demo to two beats for clarity."

**Gates (Build Scope P0):**
- [ ] "Check in with Miguel" one-click fires real outbound call in Spanish; `DriverCheckinCard` updates live from `record_proactive_checkin` writeback.
- [ ] Auto-anomaly (BE exceptions_engine tick) fires the same call without the manual click within 10s of the simulated `hos_near_cap` + silence.
- [ ] Fatigue chip animates on `load.updated` — judge can see the change from across the room.
- [ ] Spanish transcript renders correctly (accented characters, no mojibake).

### Block 5 — Polish for judges (Pair — mostly FE)

**Goal:** Features work; now they look inevitable. *(Build Plan Block 5.)*

Prioritized order (do top to bottom, stop when out of time):

1. [ ] **Dashboard chrome matches Trucker Path's visual language.** Primary blue, one alert red, neutral gray. No drop shadows on everything. Inter 14/16/20. Consistent 8px grid.
2. [ ] **Exception row pulses red convincingly.** Animated border `box-shadow` at 1.2s ease-in-out, NOT a flashing GIF, NOT a blinking background. Subtle, professional.
3. [ ] **Transcript typewriter reveal** synced to audio-ish (~30ms/char). Partial turns shimmer in; final turn "locks" visually.
4. [ ] **Live call waveform** — `<canvas>` component animated from `call.transcript` cadence (we're not wiring real audio analysis; approximate).
5. [ ] **Invoice PDF letterhead** polished: logo SVG, address block, signature line.
6. [ ] **`/demo` page** — presenter control room. Three big buttons, nothing else:
   - `Trigger detention` (POSTs `/actions/escalate-detention` with `load_id=L-12345`, `receiver_phone_override` to the teammate's phone from env)
   - `Fire anomaly` (calls `scripts/trigger_tick.py` equivalent via a small BE endpoint, or POSTs `/actions/driver-checkin` with `trigger_reason=manual` for Miguel)
   - `Play fallback` (plays `/fallback_audio/detention_call.mp3` from `public/` — pure FE, no BE)
   - `SAFE` chip bottom-right if `NEXT_PUBLIC_DEMO_SAFE_MODE=true`.
7. [ ] **Empty states + loading states** styled — Skeleton rows, "No exceptions yet" copy, etc. A judge should never see a blank white screen.
8. [ ] **One-line copy polish** on every UI element. "Escalate detention" reads better than "Escalate." "Check in with Miguel" reads better than "Call Miguel." Tight, professional.

**Gates (Build Plan):**
- [ ] A stranger looking at the dashboard for 3 seconds can tell which row is in exception.
- [ ] Transcript panel reads like a real phone call, not a chat log.
- [ ] `/demo` page fits on a single laptop screen with three buttons visible.

### Block 6 — Submission artifacts (Dev B mostly)

**Goal:** Devpost reads this, not the code. *(Build Plan Block 6.)*

- [ ] Vercel prod deploy working; custom domain optional.
- [ ] `NEXT_PUBLIC_API_BASE_URL` pointing at Fly URL, not localhost.
- [ ] README has a GIF of the detention demo at the top. 3-5 seconds of the button click → transcript shimmer → invoice pop.
- [ ] Architecture diagram (single image) in README.
- [ ] `/demo` page works on prod URL end-to-end.

**Gate (Build Plan):**
- [ ] `curl https://<vercel-url>/api/health` (if you add one) or navigating to `/` returns the dashboard with live data.
- [ ] `/demo` on prod URL: three buttons, all functional.

### Block 7 — Dry runs and ruthless cuts (Pair)

**Goal:** Break it on purpose. *(Build Plan Block 7.)*

FE focus:
- [ ] Run the 3-minute demo from `/demo` start to finish. Time it.
- [ ] Simulate Wi-Fi failure mid-detention (BE toggles `demo_safe_mode`). Dashboard must look identical.
- [ ] Browser cache purge → fresh load → first paint < 1.5s (Vercel caching handles most of this).
- [ ] Keyboard-only demo run: every trigger button reachable by Tab + Enter.

### Block 8 — Ship (Pair)

Confirm Vercel prod is live, `/demo` loads from a cold browser.

## 6. Component contracts

### `LoadTable.tsx`

**Props:**
```ts
interface LoadTableProps {
  initialLoads: Load[];        // server-fetched on SSR for fast paint
}
```

**Behavior:**
- Subscribes to `load.updated` via `useLoads()`; merges into local state by `id`.
- Renders `LoadRow` per load, sorted so exception rows are pinned to top.
- Exception rows: left-border-red-4 + `ExceptionBadge` + pulsing `box-shadow`.
- Detention timer on exception rows updates every 1s client-side (no WS dep).

### `TranscriptPanel.tsx`

**Props:**
```ts
interface TranscriptPanelProps {
  callId: UUID;
}
```

**Behavior:**
- Subscribes to `call.transcript` filtered by `call_id`.
- Renders final and partial turns; finals are visually "committed," partials shimmer.
- Typewriter reveal on new turns; skip animation if user hovers (they want to read, not wait).
- Speaker = `agent` → left-aligned, blue avatar "M"; `human` → right-aligned, gray avatar.
- Language-aware: renders `language: 'es'` turns in a slightly different font color (subtle — `text-slate-700` vs `text-slate-900`) to signal the multilingual capability without translating.

### `DriverCheckinCard.tsx`

**Props:**
```ts
interface DriverCheckinCardProps {
  driverId: UUID;
}
```

**Behavior:**
- Hydrates from `GET /api/v1/drivers/{id}/` (or the driver chunk of `listLoads`).
- Subscribes to `load.updated` filtered to this driver's active load; patches fatigue/ETA/HOS chips on event.
- Pulsing amber border when `hos_drive_remaining_minutes < 30`.
- Red pulsing border when any `exception.raised` event matches this driver id.
- "Check in with X" button bottom-right.

### `InvoiceModal.tsx`

**Props:** none (subscribes to `invoice.generated`).

**Behavior:**
- Listens via `useLatestInvoice()`; on event, opens a shadcn `Dialog` embedding `<iframe src={`/invoices/${id}/pdf`} />`.
- Modal auto-focuses a close button; Esc dismisses.
- One-click "Download" button (`<a download>`).
- **Never** re-opens automatically on re-renders — gate on the `invoice.generated` event timestamp, close only by user action.

### `TriggerButton.tsx`

**Props:**
```ts
interface TriggerButtonProps {
  variant: 'escalate_detention' | 'manual_checkin' | 'play_fallback';
  payload: Record<string, unknown>;       // load_id, driver_id, etc.
  onStart?: (response: unknown) => void;
  disabled?: boolean;
}
```

**Behavior:**
- Debounced — a second click within 2s is a no-op (BE is idempotent on `(call_id, tool_name)` but we also enforce on the FE to avoid UX noise).
- Loading spinner inside the button after click; transitions to `CallStatusBanner` state.
- On 502 `telephony_unavailable`, surfaces a toast with "Tap to play fallback audio" linking to `/demo`.

## 7. Realtime channel (Pusher)

Single channel: `dispatcher.${NEXT_PUBLIC_DISPATCHER_ID}` (→ `dispatcher.demo`).

Event handlers live in `lib/realtime.ts`, exposed as hooks. Payload shapes come from API Models §5:

| Event | Shape | Handler behavior |
|---|---|---|
| `load.updated` | `Load` | Upsert by `id` into the loads store. Re-render affected `LoadRow` + any `DriverCheckinCard` bound to this load's driver. |
| `exception.raised` | `ExceptionEvent` | Push onto the anomaly rail; fire `AnomalyBadge` pulse on the associated load/driver. |
| `call.started` | `{call_id, purpose, load_id}` | Set the affected `LoadRow`'s call status to `calling`. Open `TranscriptPanel` bound to `call_id`. |
| `call.transcript` | `TranscriptTurn & {call_id}` | Append to the `call_id`-keyed transcript buffer; if `is_final=false`, mark as partial (shimmer styling). |
| `call.ended` | `Call` | Set status to `completed`; clear transcript partials; persist full transcript to the call detail page cache. |
| `invoice.generated` | `DetentionInvoice` | Fire `useLatestInvoice()`; `InvoiceModal` auto-opens. |

**Never** rely on event ordering. On mount/reconnect, refetch `GET /api/v1/loads/` and let event replays reconcile.

**Reconnection strategy.** `pusher-js` handles reconnect; on reconnect, re-hydrate by calling `listLoads()` + `listCalls({limit: 10})`. Do NOT replay missed events — idempotency in component state + full refetch is simpler and more robust for a hackathon.

## 8. Pages

### `/` — Dispatcher dashboard (the home screen)

Server-renders `/api/v1/loads/` for fast first paint. Client hydrates Pusher. Layout:

```
┌────────────────────────────────────────────────────────────────┐
│ Header: Acme Trucking · Maria's Dispatch · UTC clock            │
├─────────────────────────────────┬──────────────────────────────┤
│ LoadTable (8 rows)              │ Right rail:                   │
│   · L-12345 🔴 pulse             │   · Anomaly feed              │
│   · L-12346                      │   · Active call transcript    │
│   · L-12347                      │     (TranscriptPanel)         │
│   · …                            │   · DriverCheckinCard × N     │
└─────────────────────────────────┴──────────────────────────────┘
```

### `/calls/[callId]`

Server-renders `/api/v1/calls/{id}/`. Full transcript, audio `<audio src={audio_url}>` when available, outcome chip, linked invoice if `detention_escalation` resolved. No WS subscribes needed — this page shows historical data. Live calls jump back to `/` to watch the live shimmer.

### `/invoices/[invoiceId]`

Server-renders `/api/v1/invoices/{id}/`. Embeds `/invoices/{id}/pdf` in an `<iframe>`. Download button. Metadata sidebar (load#, driver, call link).

### `/drivers`

Reads from `/api/v1/drivers/` (if exposed; else synthesize from `/loads/` + known driver ids). Roster of 6 drivers with `DriverCheckinCard` for each. Judges rarely click here; a nice Q&A destination.

### `/brokers`

Light: list of 5 brokers with contact info. No interactivity. A filler page for navigation completeness.

### `/demo` — Presenter control room

Three big buttons only. Bottom-right `SAFE` chip when `NEXT_PUBLIC_DEMO_SAFE_MODE=true`. Black background, giant hit targets, keyboard shortcuts `1`/`2`/`3`. Meant to be the only browser tab open on the demo laptop.

## 9. Styling rules

- **Tailwind-only.** No CSS Modules, no styled-components, no emotion.
- **shadcn primitives only** for controls (Button, Dialog, Card, Badge, Skeleton, Toast). Don't build custom modal / button / table from scratch.
- **Single alert red** (`red-600`) — don't mix red-500 and red-600. Pick one.
- **Single amber** (`amber-500`) for HOS-near-cap. Same rule.
- **One typography scale:** `text-sm` for body, `text-base` for row content, `text-lg` for card titles, `text-2xl` for page headers. Everything else is out-of-scope.
- **Animations:** prefer Tailwind's `animate-pulse` over custom keyframes. For the custom "exception pulse" use `animate-[pulse_1.2s_ease-in-out_infinite]` utility arbitrary value — once, in `LoadRow.tsx`, not scattered.

## 10. Testing strategy

We're not chasing coverage. We're protecting contract boundaries.

**Must have:**
- [ ] `scripts/check_schema_parity.ts` — smoke-run against BE `/loads` endpoint, validates `Load` shape.
- [ ] Manual rehearsal: the 3-minute arc from `/demo`, run 5 times consecutively. Timed.
- [ ] Cross-browser check: Chrome + Safari (the two laptops on stage). Firefox nice-to-have. Mobile: not a goal.

**Don't bother:**
- Jest / React Testing Library unit tests.
- E2E Playwright suites.
- Storybook.
- i18n infra (we only render `es` strings via the transcript, not in UI chrome).

## 11. Failure modes and fallbacks

| Failure | FE detection | Fallback |
|---|---|---|
| BE `/api/v1/loads/` returns 5xx | initial fetch throws | Render `ErrorBoundary` that says "Refreshing…" and retries after 2s. If 3 retries fail, show a static snapshot from `public/snapshot_loads.json`. |
| Pusher connection drops | `pusher.connection.state === 'unavailable'` | Silent reconnect; on restore, refetch `/loads`. Show a tiny gray dot top-right indicating WS status (judge-invisible). |
| `escalate-detention` returns 502 `telephony_unavailable` | fetch response body | Toast: "Using fallback audio." Navigate presenter to `/demo` fallback button. BE safe-mode should catch this upstream; this is defense-in-depth. |
| Invoice PDF render throws | route handler catches | Return a minimal HTML fallback with the invoice data rendered as a styled table. Judge can still read `$187.50`. |
| Live transcript stalls (no events for 10s mid-call) | timer in `TranscriptPanel` | Show a subtle "(reconnecting…)" line in the panel; do not unmount the panel. |

## 12. Dev loop

```bash
cd frontend
cp .env.local.example .env.local    # fill NEXT_PUBLIC_* from Vercel dashboard or team vault
pnpm install
pnpm dev                             # http://localhost:3000

# Run schema parity check against a running BE
pnpm tsx scripts/check_schema_parity.ts

# Build + preview prod bundle
pnpm build && pnpm start
```

**Deploy:** git push → Vercel auto-deploys from main. Preview URL per PR. No CI in scope.

## 13. Cross-cutting rules (every block)

- **Schema change:** Notion API Models page first → `shared/types.ts` + `backend/models/schemas.py` → update `build_scope.md` §6 + changelog entry — same PR. No partial merges.
- **New endpoint needed:** must exist in API Models §4 before you write the client call. Else stop and coordinate with BE.
- **New dependency:** justify in the changelog entry (one sentence: problem it solves). No speculative libs.
- **New WS event:** **don't.** Reshape an existing event's payload instead.
- **No unrequested refactors.** Shipping > clean.
- **Hero beat is sacred.** Any change to `LoadTable` · `TranscriptPanel` · `InvoiceModal` · `/demo` reruns the Block 7 dry run.

## 14. Known FE-side open questions

1. **`/drivers` and `/brokers` endpoint shapes** — API Models §4 doesn't fully spec a `GET /api/v1/drivers/` list endpoint. For the hackathon, we can synthesize from `/loads/` + de-dup. If BE adds a `/drivers/` endpoint, mirror it. Low urgency — judges rarely navigate there.
2. **Spanish UI chrome.** Only transcript turns render in Spanish. Dashboard chrome stays in English. If a judge presses on bilingual UX, the answer is "driver-facing is multilingual (the voice call); dispatcher-facing is English because Maria is English-speaking." Don't build an i18n system.
3. **`/demo` SAFE-mode detection** — FE currently reads `NEXT_PUBLIC_DEMO_SAFE_MODE`. A purer signal would be the BE exposing `/health` with `demo_safe_mode: bool` and the FE polling. Low urgency; env var is fine for the hackathon.
4. **Anomaly rail vs driver cards** — if both exist and fire, two places can pulse for the same event. Decide in Block 4 which takes visual priority; recommend: card pulses, rail shows a compact log entry (no pulse). Judges' eye tracks the row.

## 15. Changelog hygiene

Every push writes one file in `API_DOCS/changelog/` using the template in `changelog/README.md`. FE entries use the `FE_` prefix (`2026-04-19_1200_FE_wire-transcript-panel.md`). API/schema impact section is mandatory if `types.ts` changed. Cross-side asks go under "What the other side needs to do." Never silently diverge.

## 16. When in doubt

- **"Should I add a component?"** — Is it on the Block 5 priority list? If no, don't.
- **"Should I add a CSS file?"** — No. Tailwind.
- **"Should I add Zustand / Redux / Jotai?"** — No. `useSyncExternalStore` + React state.
- **"Should I render a PDF on the client?"** — No. Server-side via route handler.
- **"Should I handle camelCase vs snake_case at the boundary?"** — No. Leave it `snake_case` everywhere.
- **"Should I build a login screen?"** — No. Static `X-Relay-Dispatcher-Id: demo` header.
- **"Is this good enough?"** — If a judge would notice it in 30 seconds on stage, fix it. Otherwise ship.

**The demo is the product. The dashboard is the demo. Everything else is overhead. Build accordingly.**
