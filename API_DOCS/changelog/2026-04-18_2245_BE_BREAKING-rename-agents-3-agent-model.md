# BE BREAKING — 3-agent ElevenLabs rename (detention / driver / broker_update)

- **Session:** BE
- **Pushed at:** 2026-04-18 22:45 local
- **Commit(s):** uncommitted — WIP changelog
- **Phase:** Pre-Phase 0 — protocol/doc alignment before backend code lands
- **Breaking?** **yes** — env-var names change (`ELEVENLABS_AGENT_DRIVER_CHECKIN_ID` → `ELEVENLABS_AGENT_DRIVER_ID`; `ELEVENLABS_AGENT_BROKER_UPDATE_ID` added); ElevenLabs dashboard agent names change (`driver_checkin_agent` → `driver_agent`); prompt file rename (`prompts/driver_checkin_agent.md` → `prompts/driver_agent.md`). Re-activates `broker_update_agent` after it was deferred by the 2026-04-19 Build Scope narrowing.

## What changed

- **`API_DOCS/ElevenLabs_Twilio_integration.md`** — flipped scope note from 2 demo agents → 3; updated architecture diagram agent list; rewrote §2 ElevenLabs prerequisites; updated `.env.example` block with new var names + rename history; tool-roster table now has 3 columns (`detention_agent` / `driver_agent` / `broker_update_agent`); §3.6 post-call `broker_check_call` row flipped from deferred → active; §5.2 renamed `driver_checkin_agent` → `driver_agent` with a rename header note; §5.4 `broker_update_agent` section replaced (was 2-line deferral, now full config with voice / prompt / tools / Data Collection / Evaluation Criterion / concurrency note); §7 Beat 1 data-flow comment renamed `DRIVER_CHECKIN_AGENT` → `DRIVER_AGENT`; Block 0 + Block 4 checklists updated; added Block 4.5 for broker agent gates; §14 open-question on rate limits re-armed (broker batch back in play).
- **`API_DOCS/Backend_phase_guide.md`** — updated the top Scope Reconciliation box with the 3 active agents + amended deferral list (F6 IVR only); Block 0 agent-creation bullet rewrites to the new names; Block 4 [DEFERRED] broker-batch subsection replaced with an active broker-agent subsection; `prompts/driver_checkin_agent.md` → `prompts/driver_agent.md`; deferred-gates list trimmed; ruthless-cuts footer note amended.
- **`API_DOCS/build_scope.md`** — new §4.2.1 ElevenLabs agent roster table (3 agents, env vars, tool attachments, deferred note); §5.2 Stretch and §5.3 Deferred reshuffled to reflect new reality; §8 env-var table split the `ELEVENLABS_AGENT_*_ID` line to name all three + flag deferred/renamed.

## Why

User requested (this session): three ElevenLabs agents total — keep `detention_agent`, rename the check-in agent to `driver_agent`, add/re-activate `broker_update_agent` that directly calls brokers. Docs had conflicting references across files (Notion PMD §10 said "three agents" but listed four personas; `ElevenLabs_Twilio_integration.md` had narrowed to two; `Backend_phase_guide.md` Block 0 still said three but named `driver_ivr` instead of `driver`). This push picks the 3-agent truth and lands it consistently across every file in `API_DOCS/`.

## API / schema impact

- **Enums, types, endpoints, WS events:** — none.
- **Env vars (BE):**
  - `ELEVENLABS_AGENT_DRIVER_CHECKIN_ID` → `ELEVENLABS_AGENT_DRIVER_ID` (rename).
  - `ELEVENLABS_AGENT_BROKER_UPDATE_ID` — added (was never in `.env.example` after the deferral; before that it was briefly `ELEVENLABS_AGENT_BROKER_ID`).
  - `ELEVENLABS_AGENT_DRIVER_IVR_ID` — commented out in `.env.example`, kept for post-hackathon resume.
- **ElevenLabs dashboard (not code, but cross-session-visible config):**
  - `driver_checkin_agent` renamed to `driver_agent` (same agent, new label).
  - `broker_update_agent` newly provisioned; attach `TWILIO_FROM_NUMBER`; 3 tools (`get_load_details`, `get_driver_status`, `log_conversation_outcome`); Data Collection 3 items; Evaluation Criterion `broker_informed`.
- **Filesystem:**
  - `prompts/driver_checkin_agent.md` → `prompts/driver_agent.md` (move, not copy).
  - `prompts/broker_update_agent.md` — stays (was already in the tree per PMD §10).

## What the other side needs to do

- [ ] **FE:** nothing required for this push (no shared types moved). If/when a Batch Broker Updates button is wired on the dashboard, it POSTs the already-defined `/api/v1/actions/batch-broker-updates/` contract in API Models §4.1 and subscribes to `call.started` / `call.transcript` / `call.ended` on `dispatcher.demo`. §4.2.1 of `build_scope.md` is the new agent roster — worth a read.

## Files touched

- `API_DOCS/ElevenLabs_Twilio_integration.md` — 9 edits
- `API_DOCS/Backend_phase_guide.md` — 5 edits
- `API_DOCS/build_scope.md` — 4 edits
- `API_DOCS/changelog/2026-04-18_2245_BE_BREAKING-rename-agents-3-agent-model.md` — this file

## Verification

- `grep -n "driver_checkin_agent\|DRIVER_CHECKIN_AGENT\|ELEVENLABS_AGENT_DRIVER_CHECKIN" API_DOCS/ElevenLabs_Twilio_integration.md` — all remaining hits are intentional rename-history references.
- `grep -n "driver_checkin_agent\|driver_ivr_agent\|broker_update_agent\|ELEVENLABS_AGENT_" API_DOCS/Backend_phase_guide.md` — references cleanly labelled as active / deferred / renamed.
- No hero-path code touched → `rehearse_hero.py` not applicable.

## Notes / open questions

- **Interpretation assumption.** User's scoping of the rename was ambiguous on whether `driver_agent` also absorbs the inbound IVR. I went with **outbound-only** (IVR stays deferred per the existing 2026-04-19 Build Scope narrowing). If you intended a unified driver_agent that also handles inbound, say so and I'll do a short follow-up push to un-defer `driver_ivr_agent`, collapse the two personas in §5.2, and re-instate Feature 6 as P0.
- **Follow-ups outside this push's `API_DOCS/`-only scope** (tracked for the next BE push):
  1. `backend/config.py` currently has `elevenlabs_agent_driver_ivr_id` and `elevenlabs_agent_driver_checkin_id` fields. Needs rename: `driver_checkin_id` → `driver_id`; add `broker_update_id`; consider removing or commenting `driver_ivr_id`.
  2. `backend/CLAUDE.md` §10 env-var block lists `elevenlabs_agent_broker_id` and `elevenlabs_agent_driver_ivr_id`. Needs rename to match.
  3. Notion **API Models** and **PMD** pages still describe the old naming (four personas + "Proactive Check-In Agent" language). The 3-agent model should land on Notion in the next sync PR — per golden rule #1 Notion is the canonical SoT; we're ahead of it right now, which is the wrong direction.
  4. `prompts/driver_checkin_agent.md` → `prompts/driver_agent.md` file rename (alongside the BE code rename PR).
- **Demo-beat scope.** The scripted demo stays two beats. `broker_update_agent` is active but not required to fire on the timeline; it's there for judge Q&A and for the FE to exercise if bandwidth allows. Flag if you want the broker flow elevated to a third scripted beat — would need a 15-sec slot in Demo Script and a visual for the dashboard.
