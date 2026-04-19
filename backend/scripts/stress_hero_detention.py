"""End-to-end stress test against a running Relay backend.

Default target is the Heroku prod URL. Override via RELAY_BACKEND_URL.

Exercises:
  1. Hero detention lifecycle — Carlos / L-12345:
     post_call webhook → /tools/detention/confirm → /internal/invoice/generate_detention
     (expected invoice ≈ $58.75 from 47 min over-free × $75/hr seeded math).
  2. Webhook idempotency — replay same conversation_id → duplicate:true.
  3. Driver-agent urgent branch — Miguel / HOS 25m:
     post_call webhook (issues_flagged=true) → /internal/dispatcher/urgent_queue.
  4. Concurrency burst — 50 parallel GETs at /tools/driver/context.

Intentionally does NOT call /internal/call/initiate — that would hit
ElevenLabs' real outbound API and spend credits. The post_call webhook is
the exact code path ElevenLabs hits after a real call, so simulating it
validates the same lifecycle.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import statistics
import sys
import time
import uuid

import httpx

BASE = os.environ.get("RELAY_BACKEND_URL", "https://relay-truckerpath-b1b6f88e3d10.herokuapp.com")
TOKEN = os.environ.get("RELAY_INTERNAL_TOKEN", "")
SECRET = os.environ.get("ELEVENLABS_WEBHOOK_SECRET", "")

# Agent IDs from Heroku config (3-agent model).
DETENTION_AGENT_ID = "agent_6501kphrvw6vfq8ayq6a90m1k1gf"
DRIVER_AGENT_ID = "agent_9301kpjhjv5be9wsfa3sxtgek81d"

# Hero-demo IDs (seeded in data/*.json).
CARLOS_ID = "d1a2b3c4-0000-0000-0000-000000000001"
MIGUEL_ID = "d1a2b3c4-0000-0000-0000-000000000004"
HERO_LOAD_ID = "b17e9c2d-4a5f-4e88-9c12-a6bd2e4f7123"  # L-12345

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


def _sign(raw: bytes) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if not SECRET:
        return h
    ts = str(int(time.time()))
    digest = hmac.new(SECRET.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    h["ElevenLabs-Signature"] = f"t={ts},v0={digest}"
    return h


def _post_call_payload(
    *,
    conversation_id: str,
    agent_id: str,
    driver_id: str,
    load_id: str,
    data_collection: dict,
    transcript_summary: str,
    to_number: str = "+13105551234",
) -> bytes:
    body = {
        "type": "post_call_transcription",
        "event_timestamp": int(time.time()),
        "data": {
            "agent_id": agent_id,
            "conversation_id": conversation_id,
            "status": "done",
            "call_duration_secs": 94,
            "transcript": [
                {"role": "agent", "message": "Hi, this is Maya from Acme.", "time_in_call_secs": 0},
                {"role": "user", "message": "Go ahead.", "time_in_call_secs": 3},
            ],
            "metadata": {
                "phone_call": {
                    "direction": "outbound",
                    "to_number": to_number,
                    "from_number": "+16204004674",
                }
            },
            "conversation_initiation_client_data": {
                "dynamic_variables": {
                    "current_load_id": load_id,
                    "driver_id": driver_id,
                    "trigger_reason": "manual",
                    "preferred_language": "en",
                }
            },
            "analysis": {
                "call_successful": "success",
                "data_collection_results": data_collection,
                "evaluation_criteria_results": {},
                "transcript_summary": transcript_summary,
            },
        },
    }
    return json.dumps(body).encode()


async def _timed(coro):
    t0 = time.monotonic()
    res = await coro
    return res, int((time.monotonic() - t0) * 1000)


async def hero_detention(client: httpx.AsyncClient) -> dict:
    """Fire post_call → confirm_detention → generate invoice. Expect ~$58.75."""
    print(f"\n{DIM}── Step 1: hero detention (Carlos / L-12345){RESET}")
    conv_id = f"conv_stress_det_{uuid.uuid4().hex[:8]}"
    out = {"conv_id": conv_id}

    # 1a. post_call webhook (detention_agent, committed_to_pay=true).
    raw = _post_call_payload(
        conversation_id=conv_id,
        agent_id=DETENTION_AGENT_ID,
        driver_id=CARLOS_ID,
        load_id=HERO_LOAD_ID,
        data_collection={
            "committed_to_pay": {"value": True, "rationale": "Janet confirmed via email"},
            "ap_contact_name": {"value": "Janet Morales", "rationale": ""},
            "ap_contact_method": {"value": "email", "rationale": ""},
        },
        transcript_summary="Agent reached Janet in AP. Committed to processing detention. Net 30.",
    )
    r, ms = await _timed(client.post("/webhooks/elevenlabs/post_call", content=raw, headers=_sign(raw)))
    body = r.json()
    ok = r.status_code == 200 and body.get("ok") is True
    mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
    print(f"  {mark} post_call webhook                  ({ms}ms)  {body.get('data')}")
    out["post_call_ok"] = ok

    # 1b. Replay same conversation_id — must be idempotent.
    r2, ms2 = await _timed(client.post("/webhooks/elevenlabs/post_call", content=raw, headers=_sign(raw)))
    dup = r2.json().get("data", {}).get("duplicate")
    mark = f"{GREEN}✓{RESET}" if dup is True else f"{RED}✗{RESET}"
    print(f"  {mark} post_call replay → duplicate:true  ({ms2}ms)")
    out["idempotent"] = dup is True

    # 1c. confirm_detention tool (inserts detention_events row w/ committed_to_pay=true).
    r3, ms3 = await _timed(
        client.post(
            "/tools/detention/confirm",
            json={
                "load_id": HERO_LOAD_ID,
                "call_id": conv_id,
                "ap_contact_name": "Janet Morales",
                "ap_contact_method": "email",
                "ap_contact_detail": "ap@receiverxyz.example",
                "committed_to_pay": True,
                "detention_hours_confirmed": 0.78,
                "notes": "47 min over free; Net 30",
            },
        )
    )
    det = r3.json().get("data", {})
    ok3 = r3.status_code == 200 and "detention_event_id" in det
    mark = f"{GREEN}✓{RESET}" if ok3 else f"{RED}✗{RESET}"
    print(f"  {mark} confirm_detention                  ({ms3}ms)  event_id={det.get('detention_event_id','')[:8]}…")

    # 1d. Generate invoice (explicit call — avoids racing the bg task from step 1a).
    r4, ms4 = await _timed(
        client.post("/internal/invoice/generate_detention", json={"call_id": conv_id})
    )
    inv = r4.json().get("data", {})
    amt = inv.get("amount")
    expected = round(0.78 * 75.00, 2)  # $58.50 from the hours we confirmed
    ok4 = r4.status_code == 200 and amt is not None and abs(amt - expected) < 0.02
    mark = f"{GREEN}✓{RESET}" if ok4 else f"{RED}✗{RESET}"
    print(f"  {mark} invoice/generate_detention         ({ms4}ms)  amount=${amt}  status={inv.get('status')}")
    out["invoice_id"] = inv.get("invoice_id")
    out["invoice_amount"] = amt
    return out


async def driver_issues_branch(client: httpx.AsyncClient) -> dict:
    """Fire a driver_agent post_call with issues_flagged → urgent_queue."""
    print(f"\n{DIM}── Step 2: driver-agent urgent branch (Miguel){RESET}")
    conv_id = f"conv_stress_drv_{uuid.uuid4().hex[:8]}"

    raw = _post_call_payload(
        conversation_id=conv_id,
        agent_id=DRIVER_AGENT_ID,
        driver_id=MIGUEL_ID,
        load_id=HERO_LOAD_ID,
        data_collection={
            "issues_flagged": {"value": True, "rationale": "Brake warning light active"},
            "fatigue_level": {"value": "moderate", "rationale": "4 hours drive left"},
            "eta_confidence": {"value": "on_time", "rationale": ""},
        },
        transcript_summary="Driver reports brake warning light on truck 22. Routing to Pilot Needles for inspection.",
        to_number="+15205550104",
    )
    r, ms = await _timed(client.post("/webhooks/elevenlabs/post_call", content=raw, headers=_sign(raw)))
    ok = r.status_code == 200 and r.json().get("ok") is True
    mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
    print(f"  {mark} post_call webhook (driver_agent)   ({ms}ms)")

    r2, ms2 = await _timed(
        client.post("/internal/dispatcher/urgent_queue", json={"call_id": conv_id})
    )
    task = r2.json().get("data", {})
    ok2 = r2.status_code == 200 and "task_id" in task
    mark = f"{GREEN}✓{RESET}" if ok2 else f"{RED}✗{RESET}"
    print(f"  {mark} dispatcher/urgent_queue            ({ms2}ms)  task_id={task.get('task_id','')[:8]}…")
    return {"conv_id": conv_id, "task_id": task.get("task_id")}


async def concurrency_burst(client: httpx.AsyncClient, n: int = 50) -> dict:
    print(f"\n{DIM}── Step 3: {n}× parallel GET /tools/driver/context{RESET}")

    async def one():
        t0 = time.monotonic()
        r = await client.get("/tools/driver/context", params={"driver_id": CARLOS_ID})
        return r.status_code, int((time.monotonic() - t0) * 1000)

    t0 = time.monotonic()
    results = await asyncio.gather(*(one() for _ in range(n)), return_exceptions=True)
    total_ms = int((time.monotonic() - t0) * 1000)

    statuses = [s for s, _ in results if isinstance(s, int) or (isinstance(results[0], tuple))]
    lats = [ms for r in results if isinstance(r, tuple) for _, ms in [r]]
    errors = [e for e in results if isinstance(e, Exception)]
    oks = sum(1 for s, _ in results if isinstance(s, int) and s == 200) if results else 0

    p50 = int(statistics.median(lats)) if lats else 0
    p95 = int(sorted(lats)[int(len(lats) * 0.95) - 1]) if len(lats) >= 2 else (lats[0] if lats else 0)
    p99 = int(sorted(lats)[int(len(lats) * 0.99) - 1]) if len(lats) >= 2 else p95
    max_ms = max(lats) if lats else 0

    all_ok = oks == n and not errors and p95 < 1500
    mark = f"{GREEN}✓{RESET}" if all_ok else f"{RED}✗{RESET}"
    print(
        f"  {mark} {oks}/{n} 200s  wall={total_ms}ms  p50={p50}ms  p95={p95}ms  p99={p99}ms  max={max_ms}ms"
    )
    if errors:
        print(f"    {RED}errors: {[type(e).__name__ for e in errors[:3]]}{RESET}")
    return {"ok": all_ok, "p50": p50, "p95": p95, "max": max_ms, "errors": len(errors)}


async def main() -> int:
    print(f"Target: {BASE}")
    print(f"Bearer: {'set' if TOKEN else 'unset'}   HMAC secret: {'set' if SECRET else 'unset'}")

    async with httpx.AsyncClient(base_url=BASE, timeout=15.0, headers=headers()) as client:
        # Health precheck.
        r = await client.get("/health")
        h = r.json() if r.status_code == 200 else {}
        print(f"/health: {h}")
        if not h.get("db"):
            print(f"{RED}aborting: DB is not healthy{RESET}")
            return 1

        det = await hero_detention(client)
        drv = await driver_issues_branch(client)
        burst = await concurrency_burst(client, n=50)

    print(f"\n{DIM}── Summary{RESET}")
    summary = [
        ("hero post_call processed", det.get("post_call_ok")),
        ("hero idempotent replay", det.get("idempotent")),
        ("hero invoice generated", det.get("invoice_id") is not None),
        ("driver urgent task queued", drv.get("task_id") is not None),
        ("50× parallel burst clean", burst.get("ok")),
    ]
    for label, ok in summary:
        mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        print(f"  {mark} {label}")

    if det.get("conv_id"):
        print(
            f"\n{DIM}DB verification (via Supabase MCP){RESET}:\n"
            f"  SELECT * FROM voice_calls WHERE conversation_id IN "
            f"('{det['conv_id']}', '{drv['conv_id']}');\n"
            f"  SELECT id, amount, status FROM invoices WHERE call_id IN "
            f"(SELECT id FROM voice_calls WHERE conversation_id='{det['conv_id']}');\n"
            f"  SELECT id, priority, title FROM dispatcher_tasks WHERE related_call_id IN "
            f"(SELECT id FROM voice_calls WHERE conversation_id='{drv['conv_id']}');"
        )

    return 0 if all(ok for _, ok in summary) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
