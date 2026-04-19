"""One-shot outbound call to a real phone — requires real ElevenLabs creds.

Example:
    python3 -m backend.scripts.sample_outbound_call \\
        --to "+14085551212" \\
        --agent driver_agent \\
        --driver-id d1a2b3c4-0000-0000-0000-000000000001

Env required: `ELEVENLABS_API_KEY`, `ELEVENLABS_PHONE_NUMBER_ID`, the agent IDs
for whichever kind you're calling (`ELEVENLABS_AGENT_DETENTION_ID` etc.),
`RELAY_INTERNAL_TOKEN` if your server is auth-gated, and the server has to be
running at `RELAY_BACKEND_URL` (default `http://localhost:8000`).

This just hits `POST /internal/call/initiate` on your local backend — it's the
same path the dashboard will click later.
"""

from __future__ import annotations

import argparse
import asyncio
import os

import httpx


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True, help="E.164 destination number")
    parser.add_argument(
        "--agent",
        choices=["driver_agent", "detention_agent", "broker_update_agent"],
        default="driver_agent",
    )
    parser.add_argument("--driver-id", default=None)
    parser.add_argument("--load-id", default=None)
    parser.add_argument(
        "--trigger",
        default="scheduled_checkin",
        help="DriverCallTrigger value",
    )
    parser.add_argument("--first-message", default=None)
    args = parser.parse_args()

    base = os.environ.get("RELAY_BACKEND_URL", "http://localhost:8000")
    token = os.environ.get("RELAY_INTERNAL_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    payload = {
        "agent_kind": args.agent,
        "driver_id": args.driver_id,
        "load_id": args.load_id,
        "to_number": args.to,
        "trigger_reason": args.trigger,
    }
    if args.first_message:
        payload["first_message_override"] = args.first_message

    async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:
        r = await client.post("/internal/call/initiate", json=payload, headers=headers)
    print(f"status={r.status_code}")
    print(r.text)
    return 0 if r.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
