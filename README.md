# Relay

**Outbound voice agent for small-fleet dispatchers.**
Globe Hacks 2026 — Trucker Path track + ElevenLabs dual submission.

Full knowledge base: [Notion workspace](https://www.notion.so/347dab51d63481829ea2fe7cef1b0009)

## Quick start

```bash
cp .env.example .env
# Fill in secrets from 1Password / team vault
pnpm install
pnpm dev
```

## Structure

- `frontend/` — Next.js 14 dispatcher dashboard (Dev B)
- `backend/` — FastAPI webhook service for Twilio + ElevenLabs (Dev A)
- `prompts/` — ElevenLabs agent system prompts
- `shared/` — **Single source of truth** for types. Mirrors the API Models doc.
- `data/` — Seed data for demo
- `demo/` — Fallback audio + runbook

## Canonical docs

| Doc | Lives in |
| --- | --- |
| PMD, Pitch, API Models, Build Plan | Notion |
| Types (source of truth) | `shared/types.ts` + `backend/models/schemas.py` |
| Demo runbook | `demo/runbook.md` |

## Contracts

Any field-level API change must update the Notion API Models page **and** both type files in the same commit. See "Breaking-change protocol" at the bottom of that Notion page.
