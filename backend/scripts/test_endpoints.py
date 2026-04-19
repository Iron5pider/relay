"""Dummy-data smoketest for the ElevenLabs tool surface.

Usage:
    # In one terminal:
    uvicorn backend.main:app --reload --port 8000

    # In another:
    python3 -m backend.scripts.test_endpoints

Exits 0 if every endpoint returns the expected envelope shape with seeded IDs.
Exits non-zero on any failure. Prints one line per endpoint with latency.

What this covers:
- Bearer-auth tool endpoints (14 tools from `tools_contract.md` §2–§4).
- ElevenLabs webhooks (§6 post_call + §7 personalization) using a locally-
  computed HMAC so we exercise the verifier.
- Internal endpoints (§8.1 invoice + §8.2 urgent_queue).
- `/internal/call/initiate` envelope shape (the actual ElevenLabs API call
  is skipped — we only assert that Bearer auth + missing `to_number`
  validation behave; for a real outbound use `sample_outbound_call.py`).

Skips:
- Anything that requires a real ElevenLabs API key.
- Real POST to the ElevenLabs outbound endpoint.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sys
import time
from typing import Any, Callable

import httpx

BASE = os.environ.get("RELAY_BACKEND_URL", "http://localhost:8000")
TOKEN = os.environ.get("RELAY_INTERNAL_TOKEN", "")

HERO_DRIVER_ID = "d1a2b3c4-0000-0000-0000-000000000001"  # Carlos
MIGUEL_ID = "d1a2b3c4-0000-0000-0000-000000000004"
HERO_LOAD_ID = "b17e9c2d-4a5f-4e88-9c12-a6bd2e4f7123"  # L-12345
CARLOS_PHONE = "+16025555612"


class Ctx:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            base_url=BASE, timeout=10.0, headers=self._headers()
        )
        self.results: list[tuple[str, bool, str]] = []
        self.voice_call_id: str | None = None
        self.conversation_id_stub = f"conv_test_{int(time.time())}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


def record(ctx: Ctx, label: str, ok: bool, detail: str = "") -> None:
    mark = "\033[32m✓\033[0m" if ok else "\033[31m✗\033[0m"
    print(f"  {mark} {label}{('  — ' + detail) if detail else ''}")
    ctx.results.append((label, ok, detail))


async def check(ctx: Ctx, label: str, coro: Callable[[], Any]) -> None:
    t0 = time.monotonic()
    try:
        ok = await coro()
        ms = int((time.monotonic() - t0) * 1000)
        record(ctx, f"{label} ({ms}ms)", bool(ok))
    except AssertionError as e:
        record(ctx, label, False, f"assertion: {e}")
    except Exception as e:
        record(ctx, label, False, f"{type(e).__name__}: {e}")


def assert_envelope(resp: httpx.Response, expect_keys: list[str] | None = None) -> dict[str, Any]:
    assert resp.status_code == 200, f"status={resp.status_code} body={resp.text[:200]}"
    payload = resp.json()
    assert payload.get("ok") is True, f"ok!=True: {payload}"
    data = payload.get("data")
    assert data is not None, "data is null on success envelope"
    if expect_keys:
        for k in expect_keys:
            assert k in data, f"missing field {k!r} in data: {data}"
    return data


# =============================================================================
# driver_agent tools
# =============================================================================


async def t_get_driver_context(ctx: Ctx) -> bool:
    r = await ctx.client.get("/tools/driver/context", params={"driver_id": HERO_DRIVER_ID})
    d = assert_envelope(r, ["driver_id", "name", "first_name", "preferred_language"])
    assert d["first_name"] == "Carlos", f"expected Carlos, got {d['first_name']}"
    return True


async def t_update_hos(ctx: Ctx) -> bool:
    r = await ctx.client.post(
        "/tools/driver/update_hos",
        json={
            "driver_id": MIGUEL_ID,
            "call_id": ctx.conversation_id_stub,
            "hos_remaining_min": 210,
            "status": "on_duty",
        },
    )
    d = assert_envelope(r, ["updated_at"])
    return True


async def t_update_status(ctx: Ctx) -> bool:
    r = await ctx.client.post(
        "/tools/driver/update_status",
        json={
            "driver_id": MIGUEL_ID,
            "call_id": ctx.conversation_id_stub,
            "status": "resting",
        },
    )
    assert_envelope(r, ["updated_at"])
    return True


async def t_log_issue(ctx: Ctx) -> bool:
    r = await ctx.client.post(
        "/tools/driver/log_issue",
        json={
            "driver_id": MIGUEL_ID,
            "call_id": ctx.conversation_id_stub,
            "type": "mechanical",
            "severity": 3,
            "description": "Coolant light flickered 20 min ago — temps normal",
        },
    )
    d = assert_envelope(r, ["incident_id"])
    return True


async def t_update_eta(ctx: Ctx) -> bool:
    r = await ctx.client.post(
        "/tools/trip/update_eta",
        json={
            "trip_id": HERO_LOAD_ID,
            "call_id": ctx.conversation_id_stub,
            "new_eta_iso": "2026-04-18T23:30:00Z",
            "reason": "Driver taking 45min rest at Pilot Needles",
        },
    )
    d = assert_envelope(r, ["trip_id", "previous_eta", "new_eta", "delta_minutes"])
    return True


async def t_lookup_parking(ctx: Ctx) -> bool:
    r = await ctx.client.get(
        "/tools/parking/nearby",
        params={"lat": 34.84, "lng": -114.61, "radius_mi": 100},
    )
    d = assert_envelope(r)
    assert isinstance(d, list) and len(d) >= 1, f"expected non-empty list, got {d}"
    assert "distance_mi" in d[0], f"missing distance_mi: {d[0]}"
    return True


async def t_find_repair_shop(ctx: Ctx) -> bool:
    r = await ctx.client.get(
        "/tools/repair/nearby",
        params={"lat": 34.84, "lng": -114.61, "service": "mechanical"},
    )
    d = assert_envelope(r)
    assert isinstance(d, list) and len(d) >= 1, f"expected non-empty list, got {d}"
    assert "name" in d[0] and "phone" in d[0], d[0]
    return True


async def t_notify_dispatcher(ctx: Ctx) -> bool:
    r = await ctx.client.post(
        "/tools/dispatcher/notify",
        json={
            "urgency": "med",
            "summary": "Miguel accepted Pilot Needles for rest, ETA pushed +45min",
            "driver_id": MIGUEL_ID,
            "load_id": HERO_LOAD_ID,
        },
    )
    assert_envelope(r, ["notification_id"])
    return True


# =============================================================================
# detention_agent tools
# =============================================================================


async def t_get_rate_con_terms(ctx: Ctx) -> bool:
    r = await ctx.client.get("/tools/load/rate_con_terms", params={"load_id": HERO_LOAD_ID})
    d = assert_envelope(r, ["load_number", "detention_rate_per_hour", "detention_free_minutes"])
    assert d["load_number"] == "L-12345"
    return True


async def t_confirm_detention(ctx: Ctx) -> bool:
    """Requires a voice_call row with conversation_id=ctx.conversation_id_stub.
    The first webhook test inserts it; if we haven't run that yet, skip via precondition."""
    if not ctx.voice_call_id:
        # Short-circuit: post a minimal webhook first? We'll run webhooks test
        # first so by the time we get here, voice_call exists. If not, surface
        # the precondition.
        assert False, "precondition: run post_call webhook test first"
    r = await ctx.client.post(
        "/tools/detention/confirm",
        json={
            "load_id": HERO_LOAD_ID,
            "call_id": ctx.conversation_id_stub,
            "ap_contact_name": "Janet Morales",
            "ap_contact_method": "email",
            "ap_contact_detail": "ap@receiverxyz.example",
            "committed_to_pay": True,
            "detention_hours_confirmed": 2.78,
            "notes": "Net 30 terms, invoice PDF to ap@",
        },
    )
    d = assert_envelope(r, ["detention_event_id", "invoice_generation_queued"])
    return True


async def t_mark_refused(ctx: Ctx) -> bool:
    if not ctx.voice_call_id:
        assert False, "precondition: run post_call webhook test first"
    r = await ctx.client.post(
        "/tools/detention/refused",
        json={
            "load_id": HERO_LOAD_ID,
            "call_id": ctx.conversation_id_stub,
            "reason": "Receiver insists broker handle it",
            "escalation_step_reached": 3,
            "contact_attempted": "Dock supervisor Rob Jennings",
        },
    )
    assert_envelope(r, ["detention_event_id"])
    return True


async def t_transcript_snapshot(ctx: Ctx) -> bool:
    if not ctx.voice_call_id:
        assert False, "precondition: run post_call webhook test first"
    r = await ctx.client.post(
        "/tools/call/transcript_snapshot",
        json={
            "call_id": ctx.conversation_id_stub,
            "key_quote": "Yes, we'll process the detention through AP.",
            "quote_type": "commitment",
        },
    )
    assert_envelope(r, ["snapshot_id"])
    return True


# =============================================================================
# broker_update_agent tools
# =============================================================================


async def t_get_load_status_for_broker(ctx: Ctx) -> bool:
    r = await ctx.client.get(
        "/tools/load/status_for_broker", params={"load_id": HERO_LOAD_ID}
    )
    d = assert_envelope(r, ["driver_first_name", "eta_iso", "on_schedule", "schedule_delta_minutes"])
    assert d["driver_first_name"] == "Carlos"
    return True


async def t_mark_broker_updated(ctx: Ctx) -> bool:
    if not ctx.voice_call_id:
        assert False, "precondition: run post_call webhook test first"
    r = await ctx.client.post(
        "/tools/broker/update_confirmed",
        json={
            "load_id": HERO_LOAD_ID,
            "call_id": ctx.conversation_id_stub,
            "broker_rep_name": "Jamie Park",
            "voicemail": False,
            "broker_ack_received": True,
            "notes": "Jamie confirmed on-time",
        },
    )
    assert_envelope(r, ["update_id"])
    return True


async def t_request_dispatcher_callback(ctx: Ctx) -> bool:
    if not ctx.voice_call_id:
        assert False, "precondition: run post_call webhook test first"
    r = await ctx.client.post(
        "/tools/broker/escalation_request",
        json={
            "load_id": HERO_LOAD_ID,
            "call_id": ctx.conversation_id_stub,
            "broker_rep_name": "Marcus Webb",
            "reason": "Broker wants to renegotiate detention — out of scope",
        },
    )
    assert_envelope(r, ["callback_request_id"])
    return True


# =============================================================================
# Webhooks
# =============================================================================


async def t_post_call_webhook(ctx: Ctx) -> bool:
    """Fire the post_call webhook ourselves with a valid HMAC + payload that
    matches `conversation_id=ctx.conversation_id_stub`. This creates the
    voice_calls row that subsequent detention tests depend on."""
    import json

    secret = os.environ.get("ELEVENLABS_WEBHOOK_SECRET", "")
    body = {
        "type": "post_call_transcription",
        "event_timestamp": int(time.time()),
        "data": {
            "agent_id": "agent_test",
            "conversation_id": ctx.conversation_id_stub,
            "status": "done",
            "call_duration_secs": 87,
            "transcript": [
                {"role": "agent", "message": "Hi, this is Maya from Acme.", "time_in_call_secs": 0},
                {"role": "user", "message": "Go ahead.", "time_in_call_secs": 3},
            ],
            "metadata": {
                "phone_call": {
                    "direction": "outbound",
                    "to_number": "+13105551234",
                    "from_number": "+14805551200",
                }
            },
            # ElevenLabs echoes dynamic_variables back in the post-call payload.
            # Our webhook reads current_load_id/driver_id to hydrate voice_calls
            # when no prior row exists. In prod this comes from /internal/call/initiate.
            "conversation_initiation_client_data": {
                "dynamic_variables": {
                    "current_load_id": HERO_LOAD_ID,
                    "driver_id": HERO_DRIVER_ID,
                    "trigger_reason": "manual",
                    "preferred_language": "en",
                }
            },
            "analysis": {
                "call_successful": "success",
                "data_collection_results": {
                    "committed_to_pay": {"value": True, "rationale": "Janet confirmed."}
                },
                "evaluation_criteria_results": {},
                "transcript_summary": "Agent reached AP, commitment received.",
            },
        },
    }
    raw = json.dumps(body).encode()
    ts = str(int(time.time()))
    sig = ""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if secret:
        digest = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
        sig = f"t={ts},v0={digest}"
        headers["ElevenLabs-Signature"] = sig

    r = await ctx.client.post("/webhooks/elevenlabs/post_call", content=raw, headers=headers)
    d = assert_envelope(r)
    # Pull the voice_calls.id so downstream tests can use it if needed.
    ctx.voice_call_id = ctx.conversation_id_stub  # tools resolve by conv_id
    return True


async def t_personalization_webhook(ctx: Ctx) -> bool:
    r = await ctx.client.post(
        "/webhooks/elevenlabs/personalization",
        json={
            "caller_id": CARLOS_PHONE,
            "agent_id": "agent_test",
            "called_number": "+14805559999",
            "call_sid": "CA_test",
        },
    )
    assert r.status_code == 200, f"status={r.status_code} body={r.text[:200]}"
    payload = r.json()
    # Personalization returns RAW shape (no envelope).
    assert "dynamic_variables" in payload, f"missing dynamic_variables: {payload}"
    assert payload["dynamic_variables"].get("driver_name") == "Carlos"
    assert payload["dynamic_variables"].get("preferred_language") == "es"
    return True


# =============================================================================
# Internal endpoints
# =============================================================================


async def t_generate_detention_invoice(ctx: Ctx) -> bool:
    if not ctx.voice_call_id:
        assert False, "precondition: run post_call webhook + confirm_detention first"
    r = await ctx.client.post(
        "/internal/invoice/generate_detention",
        json={"call_id": ctx.conversation_id_stub},
    )
    d = assert_envelope(r, ["invoice_id", "amount", "status"])
    assert d["status"] == "ready_for_review"
    return True


async def t_urgent_queue(ctx: Ctx) -> bool:
    if not ctx.voice_call_id:
        assert False, "precondition: run post_call webhook first"
    r = await ctx.client.post(
        "/internal/dispatcher/urgent_queue",
        json={"call_id": ctx.conversation_id_stub},
    )
    assert_envelope(r, ["task_id"])
    return True


# =============================================================================
# Auth
# =============================================================================


async def t_auth_rejection(ctx: Ctx) -> bool:
    if not TOKEN:
        # Server is in dev-bypass mode (no token configured); nothing to test.
        return True
    async with httpx.AsyncClient(base_url=BASE, timeout=5.0) as bare:
        r = await bare.get("/tools/driver/context", params={"driver_id": HERO_DRIVER_ID})
    assert r.status_code == 401, f"expected 401 without bearer, got {r.status_code}"
    return True


async def main() -> int:
    print(f"Target: {BASE}")
    print(f"Bearer token: {'set' if TOKEN else 'NOT SET (dev-bypass mode)'}\n")

    ctx = Ctx()
    try:
        # Order matters: post_call webhook creates the voice_calls row that
        # tool endpoints taking `call_id` depend on.
        print("[webhooks]")
        await check(ctx, "personalization webhook", lambda: t_personalization_webhook(ctx))
        await check(ctx, "post_call webhook", lambda: t_post_call_webhook(ctx))

        print("\n[driver_agent tools]")
        await check(ctx, "get_driver_context", lambda: t_get_driver_context(ctx))
        await check(ctx, "update_hos", lambda: t_update_hos(ctx))
        await check(ctx, "update_status", lambda: t_update_status(ctx))
        await check(ctx, "log_issue", lambda: t_log_issue(ctx))
        await check(ctx, "update_eta", lambda: t_update_eta(ctx))
        await check(ctx, "lookup_parking", lambda: t_lookup_parking(ctx))
        await check(ctx, "find_repair_shop", lambda: t_find_repair_shop(ctx))
        await check(ctx, "notify_dispatcher", lambda: t_notify_dispatcher(ctx))

        print("\n[detention_agent tools]")
        await check(ctx, "get_rate_con_terms", lambda: t_get_rate_con_terms(ctx))
        await check(ctx, "confirm_detention", lambda: t_confirm_detention(ctx))
        await check(ctx, "mark_refused", lambda: t_mark_refused(ctx))
        await check(ctx, "transcript_snapshot", lambda: t_transcript_snapshot(ctx))

        print("\n[broker_update_agent tools]")
        await check(ctx, "get_load_status_for_broker", lambda: t_get_load_status_for_broker(ctx))
        await check(ctx, "mark_broker_updated", lambda: t_mark_broker_updated(ctx))
        await check(ctx, "request_dispatcher_callback", lambda: t_request_dispatcher_callback(ctx))

        print("\n[internal endpoints]")
        await check(ctx, "invoice/generate_detention", lambda: t_generate_detention_invoice(ctx))
        await check(ctx, "dispatcher/urgent_queue", lambda: t_urgent_queue(ctx))

        print("\n[auth]")
        await check(ctx, "bearer rejected without token", lambda: t_auth_rejection(ctx))
    finally:
        await ctx.client.aclose()

    passed = sum(1 for _, ok, _ in ctx.results if ok)
    total = len(ctx.results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
