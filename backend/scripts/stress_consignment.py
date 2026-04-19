"""End-to-end smoke for the dispatcher consignment surface.

Exercises:
  1. GET /dispatcher/loads/unassigned — expect >=3 rows.
  2. GET /dispatcher/load/{L-12353}/candidates — expect ranking + AI recommendation.
  3. POST /dispatcher/load/{L-12353}/assign — use the AI's recommended driver.
  4. GET /dispatcher/loads/unassigned again — expect count dropped by 1.
  5. Reject test — try to assign a disqualified driver (off-duty Sarah) to an unassigned load.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import httpx

BASE = os.environ.get("RELAY_BACKEND_URL", "https://relay-truckerpath-b1b6f88e3d10.herokuapp.com")
TOKEN = os.environ.get("RELAY_INTERNAL_TOKEN", "")

L_12353 = "b17e9c2d-4a5f-4e88-9c12-a6bd2e4f712b"
L_12354 = "b17e9c2d-4a5f-4e88-9c12-a6bd2e4f712c"
SARAH_ID = "d1a2b3c4-0000-0000-0000-000000000003"  # off-duty — should be rejected

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


async def _timed(client, method: str, url: str, **kw):
    t0 = time.monotonic()
    fn = getattr(client, method.lower())
    r = await fn(url, **kw)
    return r, int((time.monotonic() - t0) * 1000)


async def main() -> int:
    print(f"Target: {BASE}")
    fails = 0
    async with httpx.AsyncClient(base_url=BASE, timeout=15.0, headers=headers()) as client:
        # Health first.
        r = await client.get("/health")
        h = r.json() if r.status_code == 200 else {}
        if not h.get("db"):
            print(f"{RED}aborting: DB not healthy: {h}{RESET}")
            return 1

        # 1. List unassigned.
        print(f"\n{DIM}── Step 1: list unassigned loads{RESET}")
        r, ms = await _timed(client, "GET", "/dispatcher/loads/unassigned")
        body = r.json()
        count_before = body.get("data", {}).get("count", 0) if r.status_code == 200 else -1
        ok1 = r.status_code == 200 and count_before >= 3
        print(f"  {GREEN if ok1 else RED}{'✓' if ok1 else '✗'}{RESET} {count_before} unassigned  ({ms}ms)")
        if not ok1:
            fails += 1
            print(f"    body: {body}")

        # 2. Candidates for L-12353.
        print(f"\n{DIM}── Step 2: rank candidates for L-12353 (Phoenix → Dallas){RESET}")
        r, ms = await _timed(client, "GET", f"/dispatcher/load/{L_12353}/candidates")
        body = r.json()
        data = body.get("data", {}) if r.status_code == 200 else {}
        ranking = data.get("ranking", [])
        ai = data.get("ai_recommendation", {})
        qual = [c for c in ranking if c.get("qualified")]
        recommended = ai.get("recommended_driver_id", "")
        ok2 = (
            r.status_code == 200
            and len(qual) >= 1
            and recommended
            and any(c["driver_id"] == recommended for c in qual)
        )
        mark = GREEN + "✓" + RESET if ok2 else RED + "✗" + RESET
        print(f"  {mark} {len(qual)} qualified / {len(ranking)} ranked  ({ms}ms)")
        if ranking:
            top = ranking[0]
            print(
                f"    top: {top['driver_name']} ({top['driver_id'][:8]}…)  "
                f"score={top['score']}  miles={top.get('miles_to_pickup')}  "
                f"status={top['status']}  qualified={top['qualified']}"
            )
        if ai:
            print(
                f"    AI ({ai.get('confidence')}): "
                f"{ai.get('recommendation','')[:120]}{'...' if len(ai.get('recommendation',''))>120 else ''}"
            )
            print(f"    risk_flags: {ai.get('risk_flags', [])}")
        if not ok2:
            fails += 1

        # 3. Assign using the AI's recommendation.
        print(f"\n{DIM}── Step 3: POST assign{RESET}")
        if recommended:
            r, ms = await _timed(
                client,
                "POST",
                f"/dispatcher/load/{L_12353}/assign",
                json={"driver_id": recommended},
            )
            body = r.json()
            ok3 = r.status_code == 200 and body.get("data", {}).get("status") == "in_transit"
            mark = GREEN + "✓" + RESET if ok3 else RED + "✗" + RESET
            print(f"  {mark} assigned  ({ms}ms)  {body.get('data', body.get('error'))}")
            if not ok3:
                fails += 1
        else:
            print(f"  {RED}✗ skipped — no recommendation{RESET}")
            fails += 1

        # 4. Count dropped by 1.
        print(f"\n{DIM}── Step 4: list unassigned again{RESET}")
        r, ms = await _timed(client, "GET", "/dispatcher/loads/unassigned")
        count_after = r.json().get("data", {}).get("count", -1) if r.status_code == 200 else -2
        ok4 = count_after == count_before - 1
        mark = GREEN + "✓" + RESET if ok4 else RED + "✗" + RESET
        print(f"  {mark} {count_before} → {count_after}  ({ms}ms)")
        if not ok4:
            fails += 1

        # 5. Reject — assign off-duty Sarah to L-12354.
        print(f"\n{DIM}── Step 5: reject disqualified driver{RESET}")
        r, ms = await _timed(
            client,
            "POST",
            f"/dispatcher/load/{L_12354}/assign",
            json={"driver_id": SARAH_ID},
        )
        body = r.json()
        ok5 = r.status_code == 400 and body.get("error", {}).get("code") == "driver_not_qualified"
        mark = GREEN + "✓" + RESET if ok5 else RED + "✗" + RESET
        print(f"  {mark} rejected ({r.status_code})  ({ms}ms)  {body.get('error')}")
        if not ok5:
            fails += 1

    print(f"\n{'All green' if fails == 0 else f'{RED}{fails} failures{RESET}'}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
