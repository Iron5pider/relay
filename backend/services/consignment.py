"""Consignment assignment — deterministic scoring layer.

Ranks available drivers for an unassigned load using four weighted components:
  hos_headroom  (35%) — surplus HOS drive time over what the run needs
  proximity     (35%) — inverse of miles from driver's current location to pickup
  freshness     (15%) — hours since last_assigned_at (load-balances the roster)
  fatigue       (15%) — penalty for fatigue_level=high

Hard filters run before scoring: drivers with status in {off_duty, sleeper,
driving} are disqualified outright (no dispatcher call to a rolling truck, no
pulling a driver off rest). Drivers with insufficient HOS drive time to
complete the haul (with a 15% buffer) are also disqualified.

HOS data is framed as "Samsara-sourced" in the pitch — we don't have live
Samsara integration in the hackathon build, but the drivers table stores the
HOS fields we'd get from an ELD partner API and the scorer treats them as
authoritative.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import Driver, Load

EARTH_RADIUS_MI = 3958.7613
AVG_SPEED_MPH = 50.0  # trucking rule-of-thumb incl. stops; scorer uses this to convert miles → drive minutes
BUFFER_PCT = 0.15  # HOS feasibility buffer (need 15% more drive time than nominal)

# Statuses that allow a new assignment. driving/off_duty/sleeper are hard-filtered.
_ASSIGNABLE_STATUSES = {"on_duty", "ready", "resting", "at_pickup", "at_delivery"}

# Component weights — must sum to 1.0
_WEIGHTS = {"hos_headroom": 0.35, "proximity": 0.35, "freshness": 0.15, "fatigue": 0.15}

_FATIGUE_SCORE = {"low": 1.0, "unknown": 0.7, "moderate": 0.4, "high": 0.0}


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


def drive_minutes_for_miles(miles: float) -> float:
    return (miles / AVG_SPEED_MPH) * 60.0


@dataclass
class ScoreBreakdown:
    driver_id: str
    driver_name: str
    truck_number: str
    preferred_language: str
    status: str
    fatigue_level: str
    hos_drive_remaining_minutes: int
    current_lat: float | None
    current_lng: float | None
    qualified: bool
    disqualification_reason: str | None
    # Derived
    miles_to_pickup: float | None
    haul_miles: float
    haul_drive_minutes: float
    hos_needed_with_buffer: float
    hos_headroom_minutes: int
    hours_since_last_assigned: float | None
    # Components (each 0..1); total is the weighted sum × 100, rounded to 1dp
    components: dict[str, float] = field(default_factory=dict)
    total: float = 0.0
    flags: list[str] = field(default_factory=list)

    def to_public(self) -> dict[str, Any]:
        return {
            "driver_id": self.driver_id,
            "driver_name": self.driver_name,
            "truck_number": self.truck_number,
            "preferred_language": self.preferred_language,
            "status": self.status,
            "fatigue_level": self.fatigue_level,
            "hos_drive_remaining_minutes": self.hos_drive_remaining_minutes,
            "miles_to_pickup": None if self.miles_to_pickup is None else round(self.miles_to_pickup, 1),
            "haul_miles": round(self.haul_miles, 1),
            "hos_headroom_minutes": self.hos_headroom_minutes,
            "hours_since_last_assigned": (
                None if self.hours_since_last_assigned is None else round(self.hours_since_last_assigned, 1)
            ),
            "qualified": self.qualified,
            "disqualification_reason": self.disqualification_reason,
            "score": self.total,
            "components": self.components,
            "flags": self.flags,
        }


def _score_driver(driver: Driver, load: Load, now: datetime) -> ScoreBreakdown:
    # Distance to pickup (None if driver has no GPS fix).
    miles_to_pickup: float | None = None
    if driver.current_lat is not None and driver.current_lng is not None:
        miles_to_pickup = haversine_miles(
            driver.current_lat, driver.current_lng, load.pickup_lat, load.pickup_lng
        )
    # Haul length (pickup → delivery).
    haul_miles = haversine_miles(
        load.pickup_lat, load.pickup_lng, load.delivery_lat, load.delivery_lng
    )
    haul_drive_minutes = drive_minutes_for_miles(haul_miles)
    hos_needed = haul_drive_minutes * (1 + BUFFER_PCT)
    hos_headroom = int(driver.hos_drive_remaining_minutes - hos_needed)

    hours_since_assigned: float | None = None
    if driver.last_assigned_at is not None:
        delta = now - driver.last_assigned_at.replace(tzinfo=driver.last_assigned_at.tzinfo or timezone.utc)
        hours_since_assigned = max(delta.total_seconds() / 3600.0, 0.0)

    breakdown = ScoreBreakdown(
        driver_id=driver.id,
        driver_name=driver.name,
        truck_number=driver.truck_number,
        preferred_language=driver.preferred_language,
        status=driver.status,
        fatigue_level=driver.fatigue_level,
        hos_drive_remaining_minutes=driver.hos_drive_remaining_minutes,
        current_lat=driver.current_lat,
        current_lng=driver.current_lng,
        qualified=True,
        disqualification_reason=None,
        miles_to_pickup=miles_to_pickup,
        haul_miles=haul_miles,
        haul_drive_minutes=haul_drive_minutes,
        hos_needed_with_buffer=hos_needed,
        hos_headroom_minutes=hos_headroom,
        hours_since_last_assigned=hours_since_assigned,
    )

    # Hard filters.
    if driver.status not in _ASSIGNABLE_STATUSES:
        breakdown.qualified = False
        breakdown.disqualification_reason = f"status_{driver.status}"
        return breakdown
    if hos_headroom < 0:
        breakdown.qualified = False
        breakdown.disqualification_reason = "insufficient_hos"
        return breakdown
    if miles_to_pickup is None:
        breakdown.qualified = False
        breakdown.disqualification_reason = "no_gps_fix"
        return breakdown

    # Component scores (each normalized to 0..1).
    # HOS headroom — sigmoid-ish: 0 headroom → 0.0, 60 min buffer → 0.5, 240+ min → 1.0.
    hos_score = min(max(hos_headroom / 240.0, 0.0), 1.0)
    # Proximity — sweet spot is 0-50mi. 50mi = 0.75, 200mi = 0.25, 400+mi → 0.
    if miles_to_pickup <= 25:
        prox_score = 1.0
    elif miles_to_pickup <= 400:
        prox_score = max(1.0 - (miles_to_pickup - 25) / 375.0, 0.0)
    else:
        prox_score = 0.0
    # Freshness — no history = 1.0 (fresh driver); 12h since last assigned = 1.0; newly assigned = 0.3.
    if hours_since_assigned is None:
        fresh_score = 1.0
    elif hours_since_assigned >= 12:
        fresh_score = 1.0
    elif hours_since_assigned >= 4:
        fresh_score = 0.7
    elif hours_since_assigned >= 1:
        fresh_score = 0.5
    else:
        fresh_score = 0.3
    # Fatigue — lookup from table.
    fat_score = _FATIGUE_SCORE.get(driver.fatigue_level, 0.5)

    components = {
        "hos_headroom": round(hos_score, 3),
        "proximity": round(prox_score, 3),
        "freshness": round(fresh_score, 3),
        "fatigue": round(fat_score, 3),
    }
    total = (
        hos_score * _WEIGHTS["hos_headroom"]
        + prox_score * _WEIGHTS["proximity"]
        + fresh_score * _WEIGHTS["freshness"]
        + fat_score * _WEIGHTS["fatigue"]
    )
    breakdown.components = components
    breakdown.total = round(total * 100.0, 1)

    # Human-readable flags.
    flags: list[str] = []
    if hos_headroom < 60:
        flags.append("tight_hos")
    if miles_to_pickup is not None and miles_to_pickup > 150:
        flags.append("long_deadhead")
    if driver.fatigue_level == "moderate":
        flags.append("fatigue_moderate")
    if hours_since_assigned is not None and hours_since_assigned < 1:
        flags.append("just_assigned")
    breakdown.flags = flags

    return breakdown


async def rank_candidates(
    db: AsyncSession, load_id: str, top_n: int = 5
) -> tuple[Load, list[ScoreBreakdown]]:
    """Load the row, score every driver, return (load, top-N qualified + disqualified appended)."""
    load = await db.get(Load, load_id)
    if load is None:
        raise ValueError(f"load {load_id!r} not found")

    result = await db.execute(select(Driver))
    drivers = list(result.scalars().all())

    now = datetime.now(timezone.utc)
    scored = [_score_driver(d, load, now) for d in drivers]

    qualified = [s for s in scored if s.qualified]
    disqualified = [s for s in scored if not s.qualified]

    qualified.sort(key=lambda s: s.total, reverse=True)
    ranked = qualified[:top_n]

    # Keep one or two disqualified rows so the dispatcher sees *why* the roster
    # isn't deeper (e.g. "Sarah is off-duty"). Cap to avoid noise.
    ranked.extend(disqualified[:3])
    return load, ranked


__all__ = [
    "ScoreBreakdown",
    "haversine_miles",
    "rank_candidates",
]
