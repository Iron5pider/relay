"""Repair shop lookup — seeded fixture (`data/repair_shops.json`).

Per `tools_contract.md` §2.7 (`find_repair_shop`). Filters by service if given,
returns top 3 sorted by distance.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "repair_shops.json"


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 3958.7613
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _load() -> list[dict[str, Any]]:
    if not _DATA_PATH.exists():
        return []
    return json.loads(_DATA_PATH.read_text())


def nearby_repair_shops(
    lat: float,
    lng: float,
    service: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    shops = _load()
    ranked: list[tuple[float, dict[str, Any]]] = []
    for s in shops:
        slat, slng = s.get("lat"), s.get("lng")
        if slat is None or slng is None:
            continue
        if service and service not in (s.get("services") or []):
            continue
        d = _haversine_miles(lat, lng, slat, slng)
        ranked.append((d, s))
    ranked.sort(key=lambda pair: pair[0])
    out: list[dict[str, Any]] = []
    for d, s in ranked[:limit]:
        out.append(
            {
                "name": s["name"],
                "distance_mi": round(d, 2),
                "phone": s.get("phone", ""),
                "services": s.get("services", []),
                "hours": s.get("hours", ""),
                "address": s.get("address", ""),
            }
        )
    return out


__all__ = ["nearby_repair_shops"]
