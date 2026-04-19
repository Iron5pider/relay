# Changelog — FE ↔ BE sync log

> **Append-only, immutable.** One file per push. This log is how the two Claude Code sessions (FE + BE) stay in sync. Neither session may edit the other's entries, and no session may edit its own past entries. If you made a mistake, write a new entry correcting it.

---

## Rules (non-negotiable)

1. **One push = one changelog file.** No batching. No "I'll write it after lunch."
2. **Write the entry *before* you tell the user the push is done.** Not after.
3. **Filename format:** `YYYY-MM-DD_HHMM_[FE|BE]_[slug].md`
   - Use 24-hour time, local (repo host) clock.
   - Slug is kebab-case, descriptive. Bad: `misc-updates`. Good: `add-escalate-detention-endpoint`.
   - If the change breaks the other side's working code, prefix the slug with `BREAKING-` (e.g. `2026-04-18_2300_BE_BREAKING-rename-call-outcome-enum.md`) and say so at the top of the entry.
4. **Never edit another session's changelog file.** Read-only to you.
5. **Never edit your own past entries.** Write a new one that corrects.
6. **If a schema, endpoint, request/response shape, env var, or shared type changed** → populate the **API / schema impact** section, and update `build_scope.md` + `frontend/shared/types.ts` + `backend/models/schemas.py` in the same push.
7. **Stay in your lane.** FE session doesn't edit backend code; BE session doesn't edit frontend code. Cross-side needs go under **What the other side needs to do.**
8. **When in doubt about whether a change affects the other session, assume yes and flag it.**

## Reading order (every session, every time, before any edit)

1. `API_DOCS/build_scope.md` — full.
2. The most recent entries in this folder — minimum last 5, or everything since your last session, whichever is more. Files sort chronologically by filename.
3. If the code in the repo disagrees with `build_scope.md`, the **changelog wins** (it's newer). Reconcile `build_scope.md` before coding.

## Anti-patterns (don't do these)

- Vague slugs (`misc-updates.md`, `fixes.md`, `stuff.md`).
- Silent schema changes — if a type changed, it goes in the entry, full stop.
- Writing the changelog after the other session has already pulled.
- Treating old entries as editable.
- Batching a half-day's worth of work into one entry because "it's related."

---

## Entry template

Copy this block into every new entry. Delete sections that don't apply, but keep headings present (with "— none" under them) so readers know you considered them.

```markdown
# [BE|FE] <one-line summary of the push>

- **Session:** BE | FE
- **Pushed at:** YYYY-MM-DD HH:MM local
- **Commit(s):** `<short-sha>` (or "uncommitted — WIP changelog")
- **Phase:** Phase N — <phase name from Backend_phase_guide.md / FE equivalent>
- **Breaking?** no | yes (describe blast radius in one line)

## What changed

- Bullet list. One bullet per distinct change. Reference file paths.

## Why

- Motivation in 1–3 sentences. Link to the spec section this satisfies (`CLAUDE.md §X`, API Models §Y, PMD section, etc.).

## API / schema impact

- Endpoint added/changed/removed: method + path + request/response shape diff.
- Shared type added/changed/removed: field-level diff (name, type, nullability).
- Enum value added/changed/removed.
- Env var added/changed/removed.
- WebSocket event shape change.
- **If everything here is "— none," say so explicitly.** Silence is ambiguous.

## What the other side needs to do

- [ ] Concrete to-do items for the OTHER session. Keep them actionable.
- [ ] If none: "— nothing; self-contained change."

## Files touched

- `path/to/file.py` — one-line description
- `path/to/other.ts` — …

## Verification

- How you confirmed this works. Test commands, manual checks, rehearsal results.
- If the hero path was touched: did `scripts/rehearse_hero.py` pass? If not, why is this still being pushed?

## Notes / open questions

- Anything the other side should know but that doesn't fit above. Follow-ups. Known-unknowns.
```

---

## Example (good)

Filename: `2026-04-18_1430_BE_add-escalate-detention-endpoint.md`

```markdown
# BE Added POST /api/v1/actions/escalate-detention

- **Session:** BE
- **Pushed at:** 2026-04-18 14:30 local
- **Commit(s):** `a1b2c3d`
- **Phase:** Phase 3 — Hero path: exception engine + outbound call + invoice
- **Breaking?** no

## What changed

- New route `backend/routes/actions.py::escalate_detention`.
- New Pydantic models `EscalateDetentionRequest`, `EscalateDetentionResponse` in `backend/models/schemas.py`.
- Wired `services.call_orchestrator.place_outbound_call` behind the route.

## Why

Hero path per `CLAUDE.md` §5.1 + API Models §4.1. This is the endpoint the Escalate Detention button on the dashboard calls.

## API / schema impact

- **Endpoint added:** `POST /api/v1/actions/escalate-detention/`
  - Request: `{ load_id: UUID, receiver_phone_override?: E164, auto_invoice?: bool = true }`
  - Response 202: `{ call_id: UUID, twilio_call_sid: str, status: "initiated", expected_detention_amount: float }`
  - Errors: 400 `load_not_in_exception`, 404 `load_not_found`, 502 `telephony_unavailable`
- **Shared type added:** `EscalateDetentionResponse` — FE needs this in `shared/types.ts`.
- Enum / env var / WS changes: — none.

## What the other side needs to do

- [ ] Add `EscalateDetentionRequest` + `EscalateDetentionResponse` to `frontend/shared/types.ts` (shapes above).
- [ ] Wire the "Escalate Detention" button on `LoadDetail` to POST this endpoint and subscribe to `call.started` on `dispatcher.demo`.

## Files touched

- `backend/routes/actions.py` — new route
- `backend/models/schemas.py` — new request/response models
- `backend/services/call_orchestrator.py` — new `place_outbound_call`

## Verification

- `pytest backend/tests/test_hero_flow.py -x` green (Twilio + ElevenLabs mocked).
- Ran `scripts/rehearse_hero.py` against live stack → all 6 assertions pass.

## Notes / open questions

- Detention math still uses the `CLAUDE.md` §5.1 formula. Needs human confirmation on half-hour rounding before we can freeze Phase 3 (see `Backend_phase_guide.md` Known spec gaps §1).
```

---

## Example (bad — do not do this)

Filename: `updates.md` *(no timestamp, no session tag, vague slug)*

```markdown
# Backend changes

Added some endpoints and fixed bugs.
```

Why this is bad: no timestamp, no session tag, no slug, no API impact section, no to-do for the other side. The FE session can't act on this.
