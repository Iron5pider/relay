# BE Bootstrapped API_DOCS shared-contract scaffold

- **Session:** BE
- **Pushed at:** 2026-04-18 22:30 local
- **Commit(s):** uncommitted — WIP changelog (to be squashed with the next commit if the human wants)
- **Phase:** Pre-Phase 0 — infrastructure the CLAUDE.md cross-session protocol requires before either side writes code
- **Breaking?** no

## What changed

- Created `API_DOCS/build_scope.md` — cross-session shared-contract skeleton: mission, sessions/lanes, tech stack, API endpoint index, scope tiers (MVP / Stretch / Anti-goals), shared-type parity rules, WS events, env-var surface, demo flow, open gaps.
- Created `API_DOCS/changelog/README.md` — append-only log rules + entry template + good/bad examples.
- Created `API_DOCS/changelog/` folder (this file is the first entry).

## Why

`CLAUDE.md` directs both sessions to `api-docs/build_scope.md` and `api-docs/changelog/` as the canonical FE↔BE sync surface, but only `API_DOCS/Backend_phase_guide.md` existed. Without the skeleton + changelog rules, both sessions would drift or invent ad-hoc conventions. Bootstrapping before Phase 0 so every subsequent push has a home.

Note on path casing: the existing folder is `API_DOCS/` (uppercase), not `api-docs/` as written in `CLAUDE.md`. I followed the filesystem rather than the doc. Flagging so the human can decide whether to (a) rename the folder or (b) fix the `CLAUDE.md` reference in the next cleanup pass. Either works; consistency matters more than which one wins.

## API / schema impact

— none. Pure documentation / protocol scaffold. No code, schemas, endpoints, env vars, or WS events changed.

## What the other side needs to do

- [ ] **FE session, read first:** `API_DOCS/build_scope.md` top-to-bottom, then this changelog entry.
- [ ] **FE session, append:** a changelog entry linking to the FE operating contract (your CLAUDE.md / phase guide) so §2 "Sessions & lanes" of `build_scope.md` resolves to a real file. Update §2 in the same push to replace "TBD" with the actual path.
- [ ] **FE session, confirm:** path casing — are we keeping `API_DOCS/` (current filesystem) or renaming to `api-docs/` (as CLAUDE.md describes)? Lowercase is more conventional; uppercase is what's on disk. Pick one in a follow-up push.

## Files touched

- `API_DOCS/build_scope.md` — new
- `API_DOCS/changelog/README.md` — new
- `API_DOCS/changelog/2026-04-18_2230_BE_bootstrap-api-docs.md` — this file

## Verification

- `ls API_DOCS/` shows `Backend_phase_guide.md`, `build_scope.md`, `changelog/`.
- `ls API_DOCS/changelog/` shows `README.md` and this entry.
- No hero-path code touched → rehearsal not applicable.

## Notes / open questions

- `build_scope.md` §10 **"Open questions / known gaps"** duplicates the four items from `Backend_phase_guide.md` "Known spec gaps" for visibility. Source of truth is still the phase guide; if those gaps move, update both.
- Build scope intentionally points at the Notion **API Models** page + `CLAUDE.md` rather than duplicating shapes here — one source of truth per concept. This doc is a lookup and a lane marker, not a spec.
- Next BE push will be Phase 0 — FastAPI skeleton, `config.py`, `deps.py`, `/health`, Alembic init. Will land in its own changelog entry.
