# BE Added Claude Sonnet anomaly-agent layer + NavPro poller

- **Session:** BE
- **Pushed at:** 2026-04-18 23:30 local
- **Commit(s):** uncommitted — WIP on master (will squash when Block 4 lands end-to-end)
- **Phase:** Block 4 — F6b Proactive Check-In + Feature 2 Anomaly Detection (Build Scope P0)
- **Breaking?** no — purely additive (new files + additive enum values + optional field + additive WS payload key)

## What changed

- Created `backend/services/anomaly_agent.py` — Claude Sonnet 4.6 reasoning layer at the Relay ↔ NavPro seam. Forced tool use (`decide_proactive_call`), 5-min prompt cache (`cache_control: ephemeral`), 3s hard timeout via `asyncio.wait_for`. Never raises — graceful hold on any failure.
- Created `backend/services/anomaly_agent_schemas.py` — `NavProSnapshot`, `DriverContext`, `AnomalyDecision`, `HardRuleHit`, `SoftSignal`, `CallSummary`.
- Created `backend/services/navpro_poller.py` — `collect_snapshot(driver_id)` fans out `list_drivers / get_location / get_breadcrumbs / get_active_trip_eta / get_performance` via `asyncio.gather(..., return_exceptions=True)` with per-endpoint failure flags.
- Created `backend/services/exceptions_engine.py` — hard-rule / soft-signal split. Hard: `hos_drive_remaining_minutes ≤ 30`, `eta_drift ≥ 30 min`, `oor_miles_last_24h ≥ 20`. Soft: `tracking_stale > 30 min`, `missed_checkin` (>2× cadence), `missing_active_trip`, `schedule_drift`, `mild_off_route`, `navpro_degraded`, `fatigue_history`.
- Created `backend/services/checkin_scheduler.py` — tiered asyncio cron (30s for hero-adjacent drivers, 60s for others) per `NavPro_integration.md` §7. Hard-rule short-circuits Claude.
- Created `backend/prompts/anomaly_agent_system.md` — ~900-token cached system prompt. Teaches Claude the Relay-owned vs NavPro-supplied field provenance so it doesn't over-weight stale HOS beliefs.
- Created `backend/services/adapters/base.py` — `NavProAdapter` ABC. Added `get_active_trip_eta`, `get_performance`; dropped `get_hos`, `send_driver_message`, `start_webhook_listener` per NavPro v1.0 gaps (`NavPro_integration.md` §9).
- Created `backend/services/adapters/{__init__,mock_tp,navpro,samsara}.py` — adapter factory + MockTP (seed-driven) + NavProHTTP stub + Samsara stub.
- Created `backend/models/schemas.py` — canonical Pydantic shapes per `backend/CLAUDE.md` §4. Filled the previously-empty file. Includes the two additive enum values + `Call.trigger_reasoning`.
- Created `frontend/shared/types.ts` — TypeScript mirror, field-for-field parity with `schemas.py`. Filled the previously-empty file.
- Updated `backend/config.py` — added anomaly-agent settings (`anomaly_agent_enabled`, `anomaly_agent_model="claude-sonnet-4-6"`, `anomaly_agent_max_tokens`, poll intervals, `navpro_tracking_stale_after_minutes`, `navpro_qps_soft_cap`).
- Updated `backend/main.py` — lifespan hook starts `checkin_scheduler.run_forever()` task when `anomaly_agent_enabled`. `/health` now reports `claude` + `navpro` flags.
- Updated `backend/deps.py` — live `get_adapter()` + memoized `get_anthropic_client()` that returns `None` when the SDK is missing or key is unset.
- Updated `backend/requirements.txt` — added `anthropic>=0.40,<1.0`.
- Updated `API_DOCS/Backend_phase_guide.md` Block 4 "Dev A — Anomaly Detection" — replaced the one-rule sketch with the full module map + env additions + failure modes.
- Updated `API_DOCS/build_scope.md` §5.1 — added the anomaly-agent + poller as P0 Feature 2 components; §6 parity rules note the two enum adds + `trigger_reasoning` field.
- Updated `API_DOCS/ElevenLabs_Twilio_integration.md` §3 — added one-line note that outbound `driver_agent` calls may be triggered by hard rules OR Claude; downstream plumbing unchanged.
- Updated `API_DOCS/NavPro_integration.md` §1 field-provenance table + new §9.1 "How Relay closes the no-webhook, no-HOS gap."

## Why

The rule engine can't reason about silence. NavPro v1.0 is pull-only with no HOS surface (per `NavPro_integration.md` §9), which means the "driver hasn't checked in and NavPro says nothing new" case has no deterministic trigger. The Claude Sonnet layer sits exactly where that judgment belongs — at the Relay ↔ NavPro seam, composing NavPro-supplied freshness with Relay-owned state (HOS self-report, fatigue history, call history, rate-con context). See the plan at `/Users/girikmanchanda/.claude/plans/polished-finding-stallman.md` for the architecture rationale and the `project_positioning` memory for why Relay owns the heavy implementation.

## API / schema impact

- **Enum added:** `CheckinTriggerReason` += `missed_checkin` (Build Scope Feature 2) + `tracking_stale` (NavPro freshness signal). Mirrored in `schemas.py` + `types.ts`. **Notion API Models §2 needs the matching addition** (tracked as task #15 — Notion MCP sync).
- **Field added (optional):** `Call.trigger_reasoning: Optional[str]` / `string | null` — Claude's rationale, surfaced verbatim in the dashboard `AnomalyBadge` tooltip. Null for hard-rule-fired calls. Mirrored in `schemas.py` + `types.ts`.
- **Field added (optional):** `DriverCheckinRequest.trigger_reasoning` — scheduler passes Claude's rationale (or hard-rule label) through the action endpoint.
- **WS event payload:** `call.started` gains an optional `trigger_reasoning?: string` (API Models §5). Six-event invariant preserved — no new event types invented.
- **Env vars added:** `anomaly_agent_enabled`, `anomaly_agent_model`, `anomaly_agent_max_tokens`, `anomaly_agent_poll_interval_hero_seconds`, `anomaly_agent_poll_interval_default_seconds`, `navpro_tracking_stale_after_minutes`, `navpro_qps_soft_cap`. All default-valued; `.env` doesn't need to declare them.
- **Dependency added:** `anthropic>=0.40,<1.0`.

## What the other side needs to do

- [ ] **FE session:** pick up the two new `CheckinTriggerReason` values (`missed_checkin`, `tracking_stale`) + `Call.trigger_reasoning` field in any component that switches on trigger reason or renders call metadata. `AnomalyBadge` should read `trigger_reasoning` first and fall back to the `trigger_reason` label when null. See `API_DOCS/Frontend_implementation_guide.md` §5 Block 4 "DriverCheckinCard / AnomalyBadge" — add the tooltip binding.
- [ ] **FE session:** update `check_schema_parity.ts` (when it lands) to validate the two new enum values + the optional `trigger_reasoning` field.

## Files touched

- `backend/models/schemas.py` — filled (was empty); canonical shapes + enum adds + `Call.trigger_reasoning`.
- `frontend/shared/types.ts` — filled (was empty); TS mirror.
- `backend/services/__init__.py` — new (package marker).
- `backend/services/anomaly_agent.py` — new; Claude reasoning layer.
- `backend/services/anomaly_agent_schemas.py` — new; Pydantic shapes.
- `backend/services/navpro_poller.py` — new; `collect_snapshot`.
- `backend/services/exceptions_engine.py` — new; hard/soft split.
- `backend/services/checkin_scheduler.py` — new; tiered cron.
- `backend/services/adapters/__init__.py` — new; `get_adapter()` factory.
- `backend/services/adapters/base.py` — new; ABC per `NavPro_integration.md` §9 gaps.
- `backend/services/adapters/mock_tp.py` — new; seed-driven demo mode.
- `backend/services/adapters/navpro.py` — new; stub pending Block 1.5 live HTTP.
- `backend/services/adapters/samsara.py` — new; Q&A-only stub.
- `backend/prompts/anomaly_agent_system.md` — new; ~900-token cached system prompt.
- `backend/config.py` — added 7 anomaly-agent settings fields.
- `backend/deps.py` — live `get_adapter()` + `get_anthropic_client()`.
- `backend/main.py` — lifespan scheduler task + `/health` `claude`/`navpro` flags.
- `backend/requirements.txt` — added `anthropic`.
- `API_DOCS/Backend_phase_guide.md` — Block 4 "Dev A — Anomaly Detection" rewritten.
- `API_DOCS/build_scope.md` — §5.1 + §6 parity rules.
- `API_DOCS/ElevenLabs_Twilio_integration.md` — §3 trigger-source note.
- `API_DOCS/NavPro_integration.md` — §1 field-provenance + new §9.1.

## Verification

- `python3 -c "import ast; …"` AST-parses cleanly across every `backend/**.py`.
- No runtime tests (no DB, no Anthropic key in CI). Live rehearsal path:
  - `python backend/scripts/rehearse_anomaly.py --driver miguel --adapter mock` (script to be authored under Block 4) → expected `decision.should_call=true`, `trigger_reason ∈ {tracking_stale, missed_checkin, hos_near_cap}`, `reasoning` non-empty.
- Hero path untouched — `scripts/rehearse_hero.py` scope unchanged.

## Notes / open questions

- The Block 2 `routes/actions.py::driver_checkin` handler isn't landed yet, so the scheduler's trigger callback currently logs instead of firing a real HTTP POST. Wiring happens in the next push when actions.py lands.
- `NavProHTTPAdapter` raises `NotImplementedError` — intentional until Block 1.5 lands the live httpx client. Mock mode works end-to-end for the demo.
- `config.py`'s existing `elevenlabs_agent_broker_id` + `elevenlabs_agent_driver_checkin_id` env names don't match the amended `ElevenLabs_Twilio_integration.md` §2 rename (`ELEVENLABS_AGENT_BROKER_UPDATE_ID` + `ELEVENLABS_AGENT_DRIVER_ID`). Not touched this push — orthogonal to the anomaly agent; to be reconciled in a follow-up rename PR.
- `ParkingSpot` Pydantic model's `Coordinates` import in schemas is exported but unused — kept for the Notion API Models §3 shape fidelity. Delete if the linter complains.
