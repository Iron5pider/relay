# 2026-04-19 02:15 — BE · Heroku deploy + ElevenLabs env rename cleanup

## Summary

First push of the FastAPI backend to Heroku (`relay-truckerpath`). Root-level `Procfile`, `runtime.txt`, and `requirements.txt` added to make the repo Heroku-buildable from `git push heroku main`. `backend/.env` keys for the three ElevenLabs agents aligned with the canonical names `backend/config.py` actually reads.

## Changes

- **New files (repo root):**
  - `Procfile` — `web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT` plus a `release: alembic -c backend/alembic.ini upgrade head` hook so every deploy runs outstanding migrations against Supabase.
  - `runtime.txt` — `python-3.11.9`.
  - `requirements.txt` — single `-r backend/requirements.txt` line; Heroku's Python buildpack requires a root-level pin.
- **`backend/.env` keys renamed** to match `backend/config.py` (3-agent model, per `2026-04-18_2245_BE_BREAKING-rename-agents-3-agent-model.md`):
  - `ELEVENLABS_DETENTION_AGENT_ID` → `ELEVENLABS_AGENT_DETENTION_ID`
  - `ELEVENLABS_BROKER_UPDATE_AGENT_ID` → `ELEVENLABS_AGENT_BROKER_UPDATE_ID`
  - `ELEVENLABS_DRIVER_AGENT_ID` → `ELEVENLABS_AGENT_DRIVER_ID`
  - added `ELEVENLABS_PHONE_NUMBER_ID=` (empty — populate after connecting Twilio in ElevenLabs dashboard)
  - added `RELAY_INTERNAL_TOKEN=<UUID>` — Bearer token the agent sends back as `secret__relay_token` on every tool call
  - added `BACKEND_PUBLIC_URL=https://relay-truckerpath.herokuapp.com`
- **Heroku app:** `relay-truckerpath` (EU/US default region). `heroku git:remote -a relay-truckerpath` linked. All config vars populated from `.env` via `heroku config:set` (DATABASE_URL pointed at Supabase pooler; NavPro JWT + RSA keypair inlined).

## Why

- Production URL is required so ElevenLabs' agent can hit our tool endpoints — ngrok URLs rotate per-session and break mid-call.
- Alignment on agent env names stops `settings.elevenlabs_agent_*_id` from silently returning `""` and raising `RuntimeError` inside `_agent_id_for` when the orchestrator tries to place a call.

## Deploy sequence

```bash
heroku git:remote -a relay-truckerpath
heroku config:set ENVIRONMENT=prod DATABASE_URL=... (see above)
git add Procfile runtime.txt requirements.txt API_DOCS/changelog/2026-04-19_0215_BE_heroku-deploy.md
git commit -m "Heroku deploy scaffolding"
git push heroku main
heroku logs --tail -a relay-truckerpath   # verify lifespan startup + scheduler boot
curl https://relay-truckerpath.herokuapp.com/health
```

## Follow-ups

- Populate `ELEVENLABS_PHONE_NUMBER_ID` in Heroku config once teammate connects the Twilio number in the ElevenLabs dashboard.
- Point ElevenLabs webhook URLs at `https://relay-truckerpath.herokuapp.com/webhooks/elevenlabs/{post_call,personalization}`.
- Point ElevenLabs tool URLs at `https://relay-truckerpath.herokuapp.com/tools/...`.
- Update `backend/CLAUDE.md` §10 env table — still references the old `driver_ivr_id` / `broker_id` var names.
