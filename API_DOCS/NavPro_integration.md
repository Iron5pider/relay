# Relay — NavPro Integration Guide

> **Who reads this:** Dev A primarily (Block 1.5 adapter implementation); Dev B for the `load.updated` / `exception.raised` payloads that surface NavPro data. Claude Code uses it as the upstream-data reference.
>
> **Precedence:** Notion **API Models** (canonical Relay contracts) · this guide (NavPro ↔ Relay translation + gaps) · `backend/CLAUDE.md` §7 (adapter pattern) · `backend/services/adapters/navpro.py` (implementation).
>
> **Source of truth for the NavPro side:** `NavPro API.pdf` (v1.0, OAS 3.0.1, released 2026-03-31). Notion API Models §4.3 tried to infer this surface pre-release and **got several things wrong** — defer to this guide when they disagree.

---

## 1. Architecture + hybrid-mode

```
         ┌──────────────────────────────────────────────────────────────┐
         │  Relay canonical domain (Pydantic schemas — what the rest of  │
         │  the app sees: Driver, Load, Broker, ParkingSpot, Call, ...)  │
         └────────────────────────▲─────────────────────────────────────┘
                                  │ canonical types only
                         get_adapter() — factory on RELAY_ADAPTER env var
                                  │
         ┌────────────────────────┼─────────────────────────────────────┐
         │                        │                                     │
    ┌────▼──────┐          ┌──────▼────────┐                   ┌────────▼──────┐
    │ MockTPAdapter │      │ NavProAdapter  │                   │ SamsaraAdapter│
    │ reads         │      │ httpx →         │                   │ sandbox only  │
    │ data/*.json   │      │ api.truckerpath │                   │ sanity check  │
    │ (canonical)   │      │ .com/navpro     │                   │               │
    └───────────────┘      └────────┬────────┘                   └───────────────┘
                                    │ translates raw → canonical
                                    ▼
                          + fills gaps from Relay DB / seeds
                          (HOS, broker, detention, parking POIs)
```

**Why hybrid.** NavPro v1.0 exposes a subset of what Relay needs. Several Relay-domain concepts — three-clock HOS, Trucker Path consumer parking data, `Broker` entity, detention config, F6b Proactive Check-In state — have no NavPro equivalent. In `RELAY_ADAPTER=navpro` mode the adapter pulls what NavPro can provide and falls back to Relay's own state for the rest.

### Field-provenance table

| Canonical field | `RELAY_ADAPTER=mock` | `RELAY_ADAPTER=navpro` |
|---|---|---|
| `Driver.id` (UUID) | seeds | **translated** from `driver_id` (int) via `uuid5(NAVPRO_NAMESPACE, str(driver_id))` |
| `Driver.name, phone, email, truck_number` | seeds | `POST /api/driver/query` → `basic_info` (phone normalized to E.164) |
| `Driver.preferred_language` | seeds | seeds (not in NavPro; derived from driver profile metadata or Relay override) |
| `Driver.status` (`driving/on_duty/off_duty/sleeper`) | seeds | **translated** from `work_status` enum; coarse mapping (`IN_TRANSIT → driving`, else falls to seed default) |
| `Driver.current_lat, current_lng` | seeds | `POST /api/tracking/get/driver-dispatch` → `trail[last]` |
| `Driver.hos_drive/shift/cycle_remaining_minutes` | seeds | **seeds (Relay-tracked)** — NavPro v1.0 does not expose HOS clocks |
| `Driver.fatigue_level, last_checkin_at, next_scheduled_checkin_at` | seeds | **Relay DB** — populated by F6b `record_proactive_checkin` post-call webhook |
| `Load.*` (all fields) | seeds | Relay DB (seeded initially); NavPro read via `driver.driver_current_load` for ID reconciliation only |
| `Load.detention_rate_per_hour, detention_free_minutes, detention_minutes_elapsed` | seeds | **seeds / Relay DB** — no NavPro concept |
| `Broker.*` | seeds | **seeds / Relay DB** — no NavPro concept (NavPro has `customer`, not `broker`) |
| `ParkingSpot[]` (for `lookup_parking` tool) | `data/tp_parking_poi.json` | `data/tp_parking_poi.json` — NavPro POI endpoint is company-custom only, not the TP consumer parking database |
| Trip creation (outbound dispatch) | no-op | `POST /api/trip/create` with `Idempotency-Key` header |
| Document attach (BOL / POD / invoice) | no-op | `POST /api/document/add` |
| GPS breadcrumbs | seeds (synthetic tick stream) | `POST /api/tracking/get/driver-dispatch` — max 30-day range per call |
| `Call.trigger_reasoning` (2026-04-19) | n/a (not generated in pure-rule path) | **Claude Sonnet 4.6** at the seam — `backend/services/anomaly_agent.py`. Plain-English rationale for why a proactive call fired, surfaced verbatim in the `AnomalyBadge` tooltip. Null when a hard rule fired. |

---

## 2. Account + credentials prerequisites (Block 0 → 1)

**Credentials file.** `relay-credentials.json` at repo root (gitignored, line 13 of `.gitignore`). Shape:

```json
{
  "name": "relay",
  "client_id": "...",
  "jwt_token": "...",
  "public_key": "...",
  "private_key": "..."
}
```

- **JWT is pre-issued.** Signed RS256 by Trucker Path. `iat ≈ 2026-04-18`, `exp ≈ 2027-04-18` (1-year validity). No refresh needed during the hackathon.
- **`public_key` / `private_key`** are for re-signing if the issued JWT expires. Not used this weekend.
- **Never commit this file.** Already in `.gitignore`.

**Loaded lazily by `backend/config.py`** via `settings.navpro_jwt_token` / `settings.navpro_client_id` — imports succeed even when the file is absent (required for CI + `RELAY_ADAPTER=mock` mode). First access raises `FileNotFoundError` with a clear message.

---

## 3. Environment variables

```bash
# RELAY_ADAPTER chooses the upstream backend. `mock` for fresh checkouts + demo-day Wi-Fi failure;
# `navpro` for production. Flip with one env var.
RELAY_ADAPTER=mock

# Base URL — note `/navpro` path, not `/v1` (API Models §4.3 inferred wrongly)
NAVPRO_BASE_URL=https://api.truckerpath.com/navpro

# Path to the credentials file. Loaded lazily — safe to leave pointing at a missing path when RELAY_ADAPTER=mock.
NAVPRO_CREDENTIALS_PATH=./relay-credentials.json

# Reserved for future. NavPro v1.0 does NOT push webhooks; this is a placeholder for the day it does.
NAVPRO_WEBHOOK_SECRET=
```

No `NAVPRO_API_KEY` or `NAVPRO_JWT_TOKEN` in `.env` — the JWT is read from the credentials file. Don't duplicate it.

---

## 4. Base URL + authentication

| | |
|---|---|
| **Base URL** | `https://api.truckerpath.com/navpro` |
| **Auth header** | `Authorization: Bearer <jwt_token>` |
| **Content-Type** | `application/json` on POST/PUT |
| **Versioning** | v1 stable; non-breaking additions in-place; breaking → `/v2/...` with advance notice |

Every endpoint example in the PDF uses the `Authorization: Bearer` header — this is confirmed, not inferred.

### httpx client setup (in `backend/services/adapters/navpro.py`)

```python
from httpx import AsyncClient, Timeout
from backend.config import settings

def make_navpro_client() -> AsyncClient:
    return AsyncClient(
        base_url=settings.navpro_base_url,
        headers={
            "Authorization": f"Bearer {settings.navpro_jwt_token}",
            "Content-Type": "application/json",
        },
        timeout=Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0),
        http2=True,
    )
```

---

## 5. Endpoint surface (from NavPro API PDF)

### §0 Drivers
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/driver/query` | Filter drivers — body: `{driver_ids?, driver_status?, driver_created_after_time?, driver_updated_after_time?, page, size}`. Returns `{total, page, data: Driver[], page_size}`. |
| POST | `/api/driver/performance/query` | Per-driver mileage + time (oor_miles / schedule_miles / actual_miles / schedule_time / actual_time). Body: `{driver_id?, time_range: {start_time, end_time}, page, page_size}`. |
| POST | `/api/driver/invite` | Create Trucker Path accounts for drivers. |
| POST | `/api/driver/edit` | Edit driver profile. |
| DELETE | `/api/driver/delete/{driver_id}` | Remove from company; TP account persists. |

**Driver response shape** (fields we care about):
```json
{
  "driver_id": 12154,
  "basic_info": {
    "driver_first_name", "driver_last_name", "carrier", "work_status",
    "terminal", "driver_type", "driver_phone_number", "driver_email"
  },
  "driver_location": { "last_known_location", "latest_update" (ms epoch), "timezone" },
  "driver_activities": [{ "time" (ms epoch), "activities": [str] }],
  "loads": [{ "driver_assign_loads": [...], "driver_current_load": {...} }],
  "contact_detail_info": { ... },
  "license_detail_info": { ... }
}
```

`work_status` enum observed: `IN_TRANSIT` (only one sampled in docs; likely includes `ACTIVE`, `OFF_DUTY`, etc. — confirm against live response).

### §1 Vehicles
`POST /api/vehicle/{update/status|query|edit|add}` · `DELETE /api/vehicle/delete`. Vehicle response carries `vehicle_id, owner_id, vehicle_status (ACTIVE/INACTIVE), vehicle_no, vehicle_type (TRUCK/TRAILER), vehicle_vin, vehicle_make, vehicle_model, gross_vehicle_weight, trailer_type (FLATBED/VAN/REEFER/CONTAINER/DRY_BULK), assignments_drivers: {driver_ids, assign_driver_info}`.

### §2 Tracking
`POST /api/tracking/get/driver-dispatch` — the **only** source of lat/lng in NavPro v1.0. Body: `{driver_id, time_range: {start_time, end_time} (ISO 8601 UTC), date_source: APP|ELD}`. Max 30-day range. Response:
```json
{
  "trail": [{ "id", "latitude", "longitude", "time" (ISO 8601) }],
  "active_trip": { "trip_id", "eta" (ISO 8601) } | null
}
```
`active_trip` is null when the driver isn't in transit. **ELD mode** requires the driver to have bound their ELD first.

### §3 Documents
`POST /api/document/{query|edit|add}` · `DELETE /api/document/delete`. Types: `BILL_OF_LADING, PROOF_OF_DELIVERY, TRIP_SHEET, CAT_SCALE, FUEL_RECEIPT, INVOICE`, etc. Scope: `UPLOAD_FILE, INVOICE, PAYMENT`. Documents can link to customer / load / driver / vehicle.

### §4 Terminals
Driver groupings. `POST /api/terminal/{edit|create|add/member}` · `GET /api/terminal/{get/member/{id}|get/list}` · `DELETE /api/terminal/{delete/{id}|delete/member/{tid}/{mid}}`.

### §5 Users
`GET /api/users/get/all?page=&size=` — returns company users: `{user_id, user_full_name, user_email, user_rank (DRIVER|…)}`.

### §6 POIs (custom)
Company-managed POIs only. `POST /api/poi/{query|edit|edit/group|add|add/group}` · `GET /api/poi/{get/group|export}` · `DELETE /api/poi/{delete/{id}|delete/group/{id}}`. POI carries `latitude, longitude, poi_detail {street, city, state, zip_code, country, contact_number, site_instruction}, site_detail {entrance[], exit[]}` (last-mile routing paths).

> ⚠ **This is NOT the Trucker Path consumer parking database.** NavPro's POI API is for the carrier's own yards / fuel stops / customer sites. For `lookup_parking` (the Love's/Pilot/TA availability the `driver_checkin_agent` reads during `hos_near_cap`), keep using the static `data/tp_parking_poi.json` snapshot.

### §7 Trips
`POST /api/trip/create` — **the outbound dispatch primitive**. Body: `{driver_id, scheduled_start_time (ISO 8601), stop_points: TripBasicInfo[] (2…N), routing_profile_id?}`. Headers include optional `Idempotency-Key` (UUID; 24-hour replay window — same key returns same response without creating a duplicate). `stop_points` fields: `latitude, longitude, address_name, appointment_time (ISO 8601), dwell_time (min), notes`. Response: `{code, success, msg, trip_id}` (e.g., `"20260306-1"`).

### §8 Routing Profiles
`GET /api/routing-profile/list?page=&size=` — truck configurations (ft/in dimensions, weight_limit, weight_per_axle, axles, trailers, avoid_areas, avoid_bridges). The `id` feeds `trip.create`'s `routing_profile_id`.

---

## 6. Response envelope + error codes

**Every response** carries a common envelope:
```json
{ "code": 200, "success": true, "msg": "success", ...payload }
```

List endpoints add pagination: `{ "total": 1000, "page": 0, "data": [...], "page_size": 20 }`.

**Error responses use standard HTTP codes:** `400 Bad Request`, `401 Not Authorized`, `403 Forbidden`, `404 Not Found`, `500 Server Error`. Body still carries the envelope with `success: false` and an error `msg`.

Treat `401` as "JWT expired / rotated" — surface a clear error, don't retry. `403` as "client_id doesn't have scope." `5xx` as retry-once-with-backoff.

---

## 7. Rate limit + retry

**25 QPS per client** is the documented safe ceiling (integrations team recommends staying below). Above that: degraded response times, not immediate 429 — but don't exceed.

**Client-side throttle** in `NavProAdapter`: token-bucket at 20 QPS (headroom under 25). Back off on 5xx with jittered exponential retry (500ms → 1s → 2s, max 3 attempts). **No retry on 4xx** — those are semantic errors.

**Polling plan for `exceptions_engine`:**
- Hero-load drivers (`status=exception` or within 30 min of appointment): tracking poll every **30 sec**.
- All other active drivers: tracking poll every **60 sec**.
- Driver query (identity refresh): every **5 min**, page through all drivers.
- A 6-driver demo fleet generates ~12 req/min against tracking and 1 req/min against driver/query — 0.2 QPS aggregate. Well under the cap.

---

## 8. Translation tables (NavPro raw → Relay canonical)

### Driver

| NavPro field | Relay canonical | Transform |
|---|---|---|
| `driver_id` (int) | `Driver.id` (UUID str) | `uuid5(NAVPRO_NAMESPACE, str(driver_id))` — deterministic, stable across runs |
| `basic_info.driver_first_name` + `driver_last_name` | `Driver.name` | `f"{first} {last}".strip()` |
| `basic_info.driver_phone_number` (`111-222-3333`) | `Driver.phone` (E.164) | `+1` + digits(phone) — assumes US; future work for international |
| `basic_info.driver_email` | (not in canonical Driver) | discard or add to schema later |
| `basic_info.work_status` (`IN_TRANSIT` / …) | `Driver.status` (`driving` / `on_duty` / `off_duty` / `sleeper`) | coarse: `IN_TRANSIT → driving`; all else → `on_duty` pending broader sample of enum values |
| `driver_location.last_known_location` (string) | (free-text, not canonical) | log for debugging; canonical lat/lng comes from tracking |
| `driver_location.latest_update` (ms epoch) | `Driver.updated_at` (ISO 8601) | `datetime.fromtimestamp(ms/1000, tz=UTC).isoformat()` |
| n/a | `Driver.preferred_language` | seed / Relay-tracked |
| n/a | `Driver.hos_*_remaining_minutes` | seed / Relay-tracked |
| n/a | `Driver.fatigue_level`, `last_checkin_at`, `next_scheduled_checkin_at` | Relay DB (F6b writeback) |
| — | `Driver.current_lat`, `current_lng`, `truck_number` | composed: `tracking.trail[-1]` + `vehicles.query[driver].vehicle_no` |

### Trip (Relay Load → NavPro Trip on dispatch)

| Relay `Load` field | NavPro `POST /api/trip/create` field |
|---|---|
| `driver.id` (UUID) | `driver_id` (int) — reverse of the uuid5 mapping; maintain a local `navpro_driver_id ↔ canonical_uuid` table in Relay DB |
| `pickup.appointment` | `scheduled_start_time` (ISO 8601) |
| `pickup.{lat, lng, name}` | `stop_points[0].{latitude, longitude, address_name}` + `appointment_time` |
| `delivery.{lat, lng, name}` | `stop_points[1].{latitude, longitude, address_name}` + `appointment_time` |
| n/a | `routing_profile_id` — pick default from `GET /api/routing-profile/list` |
| `id` (UUID) | `Idempotency-Key` header (pass `load.id` verbatim — prevents dup trips on retry) |

### ParkingSpot (`lookup_parking` tool)

**Not sourced from NavPro.** `data/tp_parking_poi.json` is the canonical source in both modes. Shape matches `ParkingSpot` exactly.

---

## 9. Gaps — Relay concepts with no NavPro equivalent

| Relay need | NavPro status | Workaround |
|---|---|---|
| **Three-clock HOS** (drive / shift / cycle remaining_minutes) | ❌ Not in v1.0. `work_status` is a single enum. | Keep HOS as seed/DB field. Document as "Relay-tracked." If Trucker Path's ELD surface exposes HOS later, wire a separate `hos_adapter`. |
| **Trucker Path consumer parking POIs** | ❌ NavPro `/api/poi/*` is company-custom only. | `data/tp_parking_poi.json` static snapshot (8 POIs along demo corridors). |
| **Driver messaging** (`send_driver_message`) | ❌ No endpoint. | Drop from adapter ABC P0 surface. Fallback: Twilio SMS direct from `services/messaging.py` if we ever need it. |
| **Push webhooks** (geofence entry, HOS change, ETA drift, stop arrived/departed) | ❌ NavPro v1.0 is pull-only. API Models §4.3's webhook list was inferred. | `exceptions_engine` polls tracking + driver-query on a timer (see §7 polling plan). `/api/v1/webhooks/navpro/events/` stays reserved for future. |
| **Broker entity** | ❌ NavPro has `customer` (per-load) and `carrier` (per-driver), not `broker`. | Relay-only concept; seeds + Relay DB carry broker state. |
| **Detention config** (rate, free minutes, elapsed) | ❌ No concept. | Relay-only; rate-con fixtures in seeds. |
| **`driver.driver_current_load` vs Relay `Load`** | ⚠ NavPro's embedded load has `load_id (int), load_show_id, customer, origin, destination, pickup_date, delivery_date, revenue`. Origin/destination are strings. | Use for ID reconciliation only. Canonical `Load` lives in Relay DB with lat/lng, broker, detention config, status. |
| **`active_trip.eta`** | ⚠ Per-driver ETA only; no per-stop breakdown. | Accept as next-stop ETA. Sufficient for dashboard + ETA drift detection. |

### 9.1 How Relay closes the no-webhook, no-HOS gap

NavPro v1.0's pull-only nature + the missing HOS surface force Relay to reason rather than react. The **Claude anomaly agent** (`backend/services/anomaly_agent.py`) is that reasoner. It runs on every scheduler tick after the hard-rule engine has had its chance, and it's the only component that sees both domains:

- NavPro-supplied freshness (`tracking_stale_minutes`, `oor_miles`, `active_trip_eta`, `schedule_actual_time_ratio`) from `navpro_poller.collect_snapshot(driver_id)`.
- Relay-owned state (HOS self-report + age, fatigue history, last check-in, call history, rate-con context, broker relationship) from the `DriverContext`.

The output (`AnomalyDecision`) carries a `trigger_reason` that matches `CheckinTriggerReason` plus a `reasoning` string rendered verbatim in the dashboard tooltip. This is what the demo leans on when the rule engine can't explain a silent driver: the system explains itself in plain English, referencing specific signal values. See `Backend_phase_guide.md` Block 4 "Dev A — Anomaly Detection."

---

## 10. The `RELAY_ADAPTER` switch in practice

The **"use_demo"** switch the user asked for:

```bash
# Fresh checkout, no creds — demo works out of the box with seed data.
RELAY_ADAPTER=mock

# Production (Fly.io), credentials in place.
RELAY_ADAPTER=navpro

# Sanity-check against Samsara sandbox for Q&A.
RELAY_ADAPTER=samsara
```

`get_adapter()` is a one-line env read; no code in routes/services ever imports a concrete adapter class.

**What stays identical across modes:** schema shapes (all canonical Pydantic), WS event payloads, API response shapes, agent tool contracts, dashboard behavior.

**What differs:**
- `mock` → fast, offline, deterministic, no creds required.
- `navpro` → live driver identity + GPS + trip dispatch, with Relay DB / seeds filling the gap fields.

**What's identical-but-noteworthy:** HOS clocks, broker, detention config, parking POIs, F6b check-in state — these come from seeds/DB in **both** modes. Flipping to `navpro` doesn't magically give you HOS from NavPro because NavPro v1.0 doesn't have HOS.

---

## 11. Reserved webhook receiver

`POST /api/v1/webhooks/navpro/events/` is **reserved** in CLAUDE.md §5 but **not wired** as a live handler. NavPro v1.0 does not push events. When v2 or a separate push channel arrives:

- Handler signs the body with HMAC-SHA256 using `NAVPRO_WEBHOOK_SECRET`.
- Idempotency on `(provider="navpro", event_id)` via `webhook_events` table.
- Translate push events to Relay `ExceptionEvent` shape; publish `exception.raised` WS event after DB commit.

Until then: `exceptions_engine` polls.

---

## 12. Smoke test

Before Block 1.5 code lands, verify auth assumption with one curl:

```bash
# With RELAY_ADAPTER=navpro and relay-credentials.json in place.
JWT=$(python -c "from backend.config import settings; print(settings.navpro_jwt_token)")

curl -sS https://api.truckerpath.com/navpro/api/driver/query \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"page": 0, "size": 5}' | python -m json.tool
```

Expected: `{"total": N, "page": 0, "data": [Driver[]], "code": 200, "success": true, "msg": "success", "page_size": 5}` without 401. That one call confirms the Bearer assumption, the base URL path (`/navpro`), and our client_id has scope.

If you get `401`: JWT expired or client scope issue. If `404` on the URL: base URL typo (likely `/navpro/api/` is critical — there IS a `/navpro` prefix before `/api/`).

When Block 1.5 lands, promote this to `backend/scripts/test_navpro_auth.py`.

---

## 13. Open questions (non-blocking)

1. **`work_status` full enum.** PDF only shows `IN_TRANSIT`. Need to sample live to map all values to `Driver.status`. Falls back to `on_duty` for now.
2. **`routing_profile_id` default** — do we create one per truck, or share one? TBD until we see the first `routing-profile/list` response in our carrier's context.
3. **Invoice attachment via `document/add`.** The PDF shows `document_type: INVOICE` is valid; detention invoice auto-attach would `POST /api/document/add` with `link_to_load` → `load_id`. Defer until F2 detention flow stable.
4. **ELD binding for HOS.** `tracking/get/driver-dispatch` supports `date_source: ELD` but requires the driver to bind their ELD first. Not a hackathon task; park for post-demo.
