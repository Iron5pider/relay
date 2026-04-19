"""Parking lookup — seeded fixture for the hackathon.

Reads `data/tp_parking_poi.json`, computes haversine distance from the query
point, returns top-N sorted ascending by distance. Per `tools_contract.md` §2.6
(`lookup_parking`).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "tp_parking_poi.json"


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 3958.7613  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _load() -> list[dict[str, Any]]:
    if not _DATA_PATH.exists():
        return []
    return json.loads(_DATA_PATH.read_text())


def nearby_parking(
    lat: float, lng: float, radius_mi: float = 50, limit: int = 5
) -> list[dict[str, Any]]:
    spots = _load()
    out: list[tuple[float, dict[str, Any]]] = []
    for s in spots:
        slat = s.get("lat")
        slng = s.get("lng")
        if slat is None or slng is None:
            continue
        d = _haversine_miles(lat, lng, slat, slng)
        if d > radius_mi:
            continue
        out.append((d, s))
    out.sort(key=lambda pair: pair[0])
    result: list[dict[str, Any]] = []
    for d, s in out[:limit]:
        result.append(
            {
                "name": s.get("name", "Truck Stop"),
                "brand": s.get("brand", s.get("name", "Unknown").split(" ")[0]),
                "distance_mi": round(d, 2),
                "direction": s.get("direction") or s.get("exit") or "nearby",
                "address": s.get("address") or s.get("exit") or "",
                "amenities": s.get("amenities") or ["parking"],
                "est_spots_available": s.get("est_spots_available") or "unknown",
            }
        )
    return result


__all__ = ["nearby_parking"]
