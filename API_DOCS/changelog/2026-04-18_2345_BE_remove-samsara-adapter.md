# BE Remove SamsaraAdapter — scope is Trucker Path only

- **Session:** BE
- **Pushed at:** 2026-04-18 23:45 local
- **Commit(s):** uncommitted — WIP changelog
- **Phase:** Pre-Phase 0 — protocol/doc alignment before backend code lands
- **Breaking?** no — `SamsaraAdapter` was a Q&A-only stub; every method raised `NotImplementedError`. Nothing in the demo path imported it. `RELAY_ADAPTER=samsara` now errors with the new "Expected mock|navpro" message instead of returning a dead adapter.

## What changed

- **Deleted:** `backend/services/adapters/samsara.py` (stub class; every method raised `NotImplementedError("SamsaraAdapter is Q&A-only.")`).
- **`backend/services/adapters/__init__.py`** — removed the `samsara` branch from `get_adapter()` and the docstring mention; factory now accepts `mock | navpro` only. `ValueError` message updated to match.
- **`backend/services/adapters/base.py`** — module docstring and `assign_trip` docstring no longer name `SamsaraAdapter`.
- **`backend/config.py`** — removed `samsara_sandbox_key: str | None = None` field (unused since adapter registration was the only consumer).
- **`backend/CLAUDE.md`** — six edits:
  - §1 golden rule 6: "Never call NavPro/Samsara/Trucker Path directly…" → "Never call NavPro/Trucker Path directly…"
  - §1 golden rule 10: dropped the "Samsara integration is a compatibility table" sentence.
  - §2 architecture ASCII: adapter line now reads `mock | navpro`.
  - §3 project tree: removed `samsara.py` entry.
  - §7 factory snippet + the `SamsaraAdapter` Q&A-sanity-check paragraph + the talking-track line mentioning Samsara — all removed.
  - §10 Settings block: dropped `relay_adapter` comment `mock | navpro | samsara` → `mock | navpro`, removed `samsara_sandbox_key`.
  - §17 P2 list: dropped the "`SamsaraAdapter` wired up against sandbox" bullet.
- **`API_DOCS/NavPro_integration.md`** — §1 architecture diagram dropped the `SamsaraAdapter` box; §10 `RELAY_ADAPTER` switch example dropped the `samsara` sanity-check case.
- **`API_DOCS/build_scope.md`** — §5.3 Deferred list removed `SamsaraAdapter`; §8 env-var table `RELAY_ADAPTER` values reduced to `navpro | mock`.
- **`API_DOCS/Backend_phase_guide.md`** — Block 1.5 adapter checklist dropped the `samsara.py` bullet.
- **`API_DOCS/ElevenLabs_Twilio_integration.md`** — `/health` adapter enum reduced to `navpro|mock`.

## Why

User scope call: Relay is and only is a command center on top of Trucker Path / NavPro (per the positioning memory — Relay-owned vs NavPro-supplied fields). The Samsara adapter existed as a Q&A-only portability demo — "could you swap in Samsara?" — but it is now out of scope. Keeping an obviously-stubbed class around invites drift (people see the method signatures and assume they work) and adds noise to every file that enumerates adapter options. Removing it makes the adapter surface truthful: one production adapter, one mock for Wi-Fi fallback, zero half-finished implementations.

## API / schema impact

- **Endpoints / request / response shapes:** — none.
- **Shared types / enums:** — none.
- **WebSocket events:** — none.
- **Env vars (BE):**
  - `RELAY_ADAPTER` — legal values reduced from `mock | navpro | samsara` to `mock | navpro`. `navpro` is still the production default (per 2026-04-18 adapter flip). Existing `.env` files with `RELAY_ADAPTER=samsara` will now fail startup with a clear `ValueError` from `get_adapter()`.
  - `SAMSARA_SANDBOX_KEY` — removed from `Settings`; silently ignored if set in `.env` (Pydantic Settings has `extra="ignore"`).
- **Filesystem:**
  - `backend/services/adapters/samsara.py` — deleted.

## What the other side needs to do

- [ ] **FE:** nothing required — no shared types moved, no endpoints touched. If any `.env` on the FE side referenced `RELAY_ADAPTER=samsara` it should be changed to `navpro` (production) or `mock` (offline).

## Files touched

- `backend/services/adapters/samsara.py` — **deleted**
- `backend/services/adapters/__init__.py` — removed samsara branch + docstring update
- `backend/services/adapters/base.py` — docstring cleanup (2 spots)
- `backend/config.py` — dropped `samsara_sandbox_key`
- `backend/CLAUDE.md` — 6 edits across §1, §2, §3, §7, §10, §17
- `API_DOCS/NavPro_integration.md` — 2 edits (§1 diagram, §10 switch example)
- `API_DOCS/build_scope.md` — 2 edits (§5.3, §8)
- `API_DOCS/Backend_phase_guide.md` — 1 edit (Block 1.5)
- `API_DOCS/ElevenLabs_Twilio_integration.md` — 1 edit (`/health` adapter enum)
- `API_DOCS/changelog/2026-04-18_2345_BE_remove-samsara-adapter.md` — this file

## Verification

- `grep -rni 'samsara' backend/ API_DOCS/` — only remaining hits are in the **historical** changelog `2026-04-18_2330_BE_anomaly-agent.md` lines 18 and 62, which are append-only and correctly reference the past state.
- Factory behavior: `RELAY_ADAPTER=mock` and `RELAY_ADAPTER=navpro` still resolve; `RELAY_ADAPTER=samsara` raises `ValueError: Unknown RELAY_ADAPTER: 'samsara'. Expected mock|navpro.`
- No hero-path code touched → `rehearse_hero.py` not applicable.

## Notes / open questions

- **Notion API Models §4.3** previously held a Samsara compatibility map referenced from `CLAUDE.md` §7. That section should be struck or retitled on Notion in the next sync PR — per golden rule #1 the Notion page is canonical and is now ahead of the code in the wrong direction (it still advertises an adapter we deleted). Flag for the human devs to prune.
- **Reversibility.** Trivial — if we ever want Samsara back, re-add `samsara.py`, re-register in the factory, and restore the env-var value. The PDF reference at `developers.samsara.com` stays documented in this changelog for discoverability.
