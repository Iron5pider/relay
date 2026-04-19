"""End-to-end smoke for the dashboard read endpoints + POD/send mutations.

Exercises the four surfaces:
  1. Fleet live — /dispatcher/fleet/live + driver detail + timeline
  2. Detentions — /dispatcher/detentions/active + detail
  3. Invoices  — /dispatcher/invoices + detail
  4. POD + send — POST /dispatcher/load/{id}/pod, POST /dispatcher/invoices/{id}/send

Uses the hero demo IDs, so detention + invoice scenarios are the ones
our stress_hero_detention.py already created — this script is purely
read-side + two state transitions.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import httpx

BASE = os.environ.get("RELAY_BACKEND_URL", "https://relay-truckerpath-b1b6f88e3d10.herokuapp.com")
TOKEN = os.environ.get("RELAY_INTERNAL_TOKEN", "")

HERO_DRIVER_ID = "d1a2b3c4-0000-0000-0000-000000000001"  # Carlos
HERO_LOAD_ID = "b17e9c2d-4a5f-4e88-9c12-a6bd2e4f7123"  # L-12345 (in detention)

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


async def _timed(client, method: str, url: str, **kw):
    t0 = time.monotonic()
    fn = getattr(client, method.lower())
    r = await fn(url, **kw)
    return r, int((time.monotonic() - t0) * 1000)


def _mark(ok_: bool) -> str:
    return GREEN + "✓" + RESET if ok_ else RED + "✗" + RESET


async def main() -> int:
    print(f"Target: {BASE}\n")
    fails = 0
    async with httpx.AsyncClient(base_url=BASE, timeout=15.0, headers=headers()) as client:
        # === 1. Fleet live ===
        print(f"{DIM}── Section 1: fleet live feed{RESET}")
        r, ms = await _timed(client, "GET", "/dispatcher/fleet/live")
        body = r.json() if r.status_code == 200 else {}
        data = body.get("data", {})
        ok_ = r.status_code == 200 and data.get("count", 0) >= 6
        fails += 0 if ok_ else 1
        print(f"  {_mark(ok_)} /fleet/live  ({ms}ms)  {data.get('count')} drivers  adapter={data.get('adapter')}")
        if ok_:
            with_loads = sum(1 for d in data.get("drivers", []) if d.get("active_load"))
            print(f"    {with_loads} drivers have active loads")

        r, ms = await _timed(client, "GET", f"/dispatcher/driver/{HERO_DRIVER_ID}")
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        ok_ = r.status_code == 200 and d.get("name") == "Carlos Ramirez"
        fails += 0 if ok_ else 1
        print(
            f"  {_mark(ok_)} /driver/{HERO_DRIVER_ID[:8]}…  ({ms}ms)  "
            f"name={d.get('name')}  status={d.get('status')}  recent_calls={len(d.get('recent_calls', []))}"
        )

        r, ms = await _timed(client, "GET", f"/dispatcher/driver/{HERO_DRIVER_ID}/timeline")
        t = r.json().get("data", {}) if r.status_code == 200 else {}
        ok_ = r.status_code == 200 and t.get("count", 0) >= 1
        fails += 0 if ok_ else 1
        print(f"  {_mark(ok_)} /driver/.../timeline  ({ms}ms)  {t.get('count')} events")
        for ev in t.get("events", [])[:3]:
            print(f"      · {ev.get('timestamp','')}  {ev.get('kind')} — {ev.get('label','')[:60]}")

        # === 2. Detentions ===
        print(f"\n{DIM}── Section 2: detention live view{RESET}")
        r, ms = await _timed(client, "GET", "/dispatcher/detentions/active")
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        ok_ = r.status_code == 200 and d.get("count", 0) >= 1
        fails += 0 if ok_ else 1
        print(f"  {_mark(ok_)} /detentions/active  ({ms}ms)  {d.get('count')} loads in detention")
        for row in d.get("detentions", [])[:2]:
            c = row.get("clock", {})
            print(
                f"      · {row.get('load_number')}  past_free={c.get('minutes_past_free')}min  "
                f"projected=${c.get('projected_amount')}  call_fired={row.get('call_fired')}  "
                f"invoice={row.get('invoice_status')}"
            )

        r, ms = await _timed(client, "GET", f"/dispatcher/detention/{HERO_LOAD_ID}")
        body = r.json().get("data", {}) if r.status_code == 200 else {}
        ok_ = r.status_code == 200 and body.get("load", {}).get("load_number") == "L-12345"
        fails += 0 if ok_ else 1
        calls = body.get("calls", [])
        events = body.get("events", [])
        print(
            f"  {_mark(ok_)} /detention/L-12345  ({ms}ms)  "
            f"{len(calls)} calls / {len(events)} detention_events / "
            f"invoice={(body.get('invoice') or {}).get('status')}"
        )

        # === 3. Invoices ===
        print(f"\n{DIM}── Section 3: invoices{RESET}")
        r, ms = await _timed(client, "GET", "/dispatcher/invoices")
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        invoices = d.get("invoices", [])
        ok_ = r.status_code == 200 and len(invoices) >= 1
        fails += 0 if ok_ else 1
        print(f"  {_mark(ok_)} /invoices  ({ms}ms)  {len(invoices)} rows  totals={d.get('totals')}")

        target_inv = None
        # Prefer one that's still ready_for_review so the send test works.
        for inv in invoices:
            if inv.get("status") == "ready_for_review":
                target_inv = inv
                break
        if target_inv is None and invoices:
            target_inv = invoices[0]

        if target_inv:
            r, ms = await _timed(
                client, "GET", f"/dispatcher/invoices/{target_inv['invoice_id']}"
            )
            d = r.json().get("data", {}) if r.status_code == 200 else {}
            ok_ = r.status_code == 200 and d.get("invoice_id") == target_inv["invoice_id"]
            fails += 0 if ok_ else 1
            print(
                f"  {_mark(ok_)} /invoices/{target_inv['invoice_id'][:8]}…  ({ms}ms)  "
                f"amount=${d.get('amount')}  status={d.get('status')}"
            )

            # === 4a. Send invoice ===
            print(f"\n{DIM}── Section 4a: POST invoice send{RESET}")
            if target_inv.get("status") == "ready_for_review":
                r, ms = await _timed(
                    client,
                    "POST",
                    f"/dispatcher/invoices/{target_inv['invoice_id']}/send",
                    json={"to_email": "ap@receiverxyz.example"},
                )
                body = r.json()
                sent = body.get("data", {}) if r.status_code == 200 else {}
                ok_ = r.status_code == 200 and sent.get("status") == "sent"
                fails += 0 if ok_ else 1
                print(
                    f"  {_mark(ok_)} sent  ({ms}ms)  status={sent.get('status')}  "
                    f"sent_at={sent.get('sent_at')}"
                )
            else:
                print(f"  {DIM}skipped — invoice already sent{RESET}")

        # === 4b. Record POD for hero load ===
        print(f"\n{DIM}── Section 4b: POST POD record{RESET}")
        r, ms = await _timed(
            client,
            "POST",
            f"/dispatcher/load/{HERO_LOAD_ID}/pod",
            json={
                "pod_url": "https://storage.relay.app/pod/L-12345.jpg",
                "signed_by": "Janet Morales (Receiver XYZ AP)",
            },
        )
        body = r.json()
        data = body.get("data", {}) if r.status_code == 200 else {}
        err = body.get("error", {}) if r.status_code != 200 else {}
        # Accept 200 (fresh record) OR 409 already_recorded (idempotent on re-run).
        ok_ = r.status_code == 200 or err.get("code") == "pod_already_recorded"
        fails += 0 if ok_ else 1
        if r.status_code == 200:
            print(f"  {_mark(ok_)} POD recorded  ({ms}ms)  signed_by={data.get('pod_signed_by')}")
        else:
            print(f"  {_mark(ok_)} idempotent — {err.get('code')}  ({ms}ms)")

    print(f"\n{'All green' if fails == 0 else f'{RED}{fails} failures{RESET}'}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
