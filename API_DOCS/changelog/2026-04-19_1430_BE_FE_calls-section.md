# 2026-04-19 14:30 — BE + FE · Calls section (list + full detail modal)

## Summary

Every ElevenLabs post_call webhook lands rich data (evaluation criteria, data collection fields with rationale, transcript with tool calls, termination reason, cost, phone metadata). Until this pass the only way the dispatcher could see any of it was as a compressed summary inside driver/detention pages. Now there's a dedicated `/dashboard/calls` section with a filterable list + a 4-tab modal showing everything.

## Backend

### Migration `20260419_0004`
- `voice_calls.termination_reason TEXT NULL` — "Missing required dynamic variables…", "voicemail detected", "caller hangup". Previously dropped by the webhook.

### Webhook `backend/routes/webhooks_elevenlabs.py`
- Now persists `data.metadata.termination_reason` into the new column.
- Threads `data.metadata.cost`, `data.metadata.phone_call`, and `data.has_audio` into `analysis_json` so the detail endpoint can surface them without additional columns.
- Duration falls back to `metadata.call_duration_secs` when the top-level field is absent.

### New routes (`backend/routes/dashboard.py`, Bearer-protected)
- **`GET /dispatcher/calls`** — list, filterable by `agent_id / purpose / outcome / call_status / driver_id / load_id`. Returns each row with summary metadata + `termination_reason`, `call_summary_title`, `transcript_summary`, `has_audio`, `cost`.
- **`GET /dispatcher/calls/{call_id}`** — accepts either `voice_calls.id` or `voice_calls.conversation_id`. Returns the full shape: summary fields, phone_call metadata, transcript turns (role/message/time/tool_calls/interrupted), evaluation criteria (normalized list, failures first), data collection fields (with rationale + schema description, useful-first ordering), linked driver/load/broker lites.

Two private composers added: `_extract_evaluation_criteria`, `_extract_data_collection`, `_transcript_turns`. They handle both dict-of-dicts and list-of-dicts shapes ElevenLabs occasionally emits.

## Frontend

### `/dashboard/calls` page
Single client component at `frontend/app/dashboard/calls/page.tsx` mirroring the drivers-page pattern:
- Filter bar: search box (conversation / summary / termination_reason), purpose select, outcome select.
- Table: started_at · direction icon · purpose · outcome pill · status pill · trigger_reason · length · summary/reason preview.
- Polls every 10s (same cadence as other dashboard pages).
- Row click opens a 620px right-anchored modal with 4 tabs:
  1. **Overview** — summary, termination reason, trigger reasoning, metadata grid (agent/direction/from/to/call_sid/phone_number_id/timestamps), linked driver/load/broker.
  2. **Transcript** — chat bubbles, agent left/gray, human right/red, `+m:ss` timestamp per turn, tool_calls rendered as chips, `· interrupted` tag when relevant.
  3. **Evaluation** — 6 criteria with green/red/gray pills (failures sorted first), rationale underneath each.
  4. **Data** — 14 fields in priority order (issues_flagged first, repair_shop_selected last), collapsed to primary 6 with "show all" toggle, showing value + schema description + rationale.

### Sidebar
- `frontend/components/dashboard/NavSidebar.tsx` — new `PhoneCall` icon entry between Billing and Drivers.

### API client + types
- `frontend/lib/api.ts` — `api.callsList(filters?)`, `api.callDetail(id)` helpers.
- `frontend/shared/types.ts` — new `CallListRow`, `CallDetail`, `EvaluationCriterion`, `DataCollectionField`, `CallTranscriptTurn`, `CallPhoneMeta` interfaces mirroring backend shapes. Canonical `Call` kept untouched.

## Verification

```bash
# Backend
python3 -c "import ast, pathlib
for p in pathlib.Path('backend').rglob('*.py'): ast.parse(p.read_text())"

# Deploy + smoke
git push heroku main
curl "https://relay-truckerpath-b1b6f88e3d10.herokuapp.com/dispatcher/calls?limit=5" \
  -H "Authorization: Bearer $RELAY_INTERNAL_TOKEN"
curl "https://relay-truckerpath-b1b6f88e3d10.herokuapp.com/dispatcher/calls/conv-0013-demo" \
  -H "Authorization: Bearer $RELAY_INTERNAL_TOKEN"

# Frontend
cd frontend && npm run dev
# Visit http://localhost:3000/dashboard/calls
```

Green gates (all passed):
- List returns current voice_calls count (13 rows in prod).
- Detail returns normalized `evaluation_criteria_results` + `data_collection_results` + `transcript` shapes (empty arrays when seed rows have no analysis yet, populated when real webhooks land).
- TypeScript compilation of new frontend files has zero errors (pre-existing TS warnings in NavSidebar/layout.tsx are not introduced by this PR).

## Out of scope (captured)
- Audio playback (separate post-call-audio webhook not yet wired).
- Transcript full-text search.
- Pagination beyond limit=100 (hackathon scope).
- Cost aggregation/totals strip.
- Back-populating the normalized `transcript_turns` table.
