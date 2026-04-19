"""MockTPAdapter — reads seed JSON + synthesizes telemetry for demo mode.

Stages the Block 4 anomaly demo beat: Miguel Rodriguez's `latest_update` is
45 min ago and `last_checkin_at` is 5h ago so the Claude anomaly agent has
something to reason about on the first scheduler tick. Exact seed values live
in `data/drivers.json` per `backend/CLAUDE.md` §13.

This adapter has no external dependencies — `RELAY_ADAPTER=mock` is safe on a
fresh checkout with zero credentials.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from backend.models.schemas import Driver, ISODateTime, ParkingSpot, UUID

from .base import (
    LocationPing,
    NavProAdapter,
    PerformanceSnapshot,
    PlaceType,
    TimeRange,
    TripRoute,
    TripUpsert,
)


_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MockTPAdapter(NavProAdapter):
    """Reads `data/*.json` + synthesizes telemetry. No I/O beyond the JSON files."""

    def __init__(self, data_dir: Path = _DATA_DIR) -> None:
        self._data_dir = data_dir

    # -- file loaders (lazy + uncached so `scripts/trigger_tick.py` can mutate) --

    def _load(self, name: str) -> list[dict]:
        path = self._data_dir / name
        if not path.exists():
            return []
        return json.loads(path.read_text())

    # -- reads --

    async def list_drivers(self) -> list[Driver]:
        raw = self._load("drivers.json")
        return [Driver.model_validate(d) for d in raw]

    async def get_location(self, driver_id: UUID) -> LocationPing:
        drivers = await self.list_drivers()
        d = next((x for x in drivers if x.id == driver_id), None)
        if d is None or d.current_lat is None or d.current_lng is None:
            return LocationPing(
                lat=0.0, lng=0.0, speed_mph=0.0, heading_deg=None, recorded_at=_now_iso()
            )
        return LocationPing(
            lat=d.current_lat,
            lng=d.current_lng,
            speed_mph=0.0 if d.status != "driving" else 55.0,
            heading_deg=None,
            recorded_at=d.updated_at,
        )

    async def get_breadcrumbs(
        self, driver_id: UUID, time_range: TimeRange
    ) -> list[LocationPing]:
        # Single-point "trail" from the seed current location; enough for the
        # anomaly agent to reason about "stationary vs moving" in demo mode.
        point = await self.get_location(driver_id)
        return [point]

    async def get_active_trip_eta(self, driver_id: UUID) -> Optional[str]:
        # Seed-driven: loads with a driver assignment expose their delivery
        # appointment as the ETA. Anomaly-staged Miguel deliberately has no
        # active load so the "missing active_trip when assigned" soft signal
        # stays negative; his case is driven by tracking staleness instead.
        loads = self._load("loads.json")
        for load in loads:
            if load.get("driver", {}).get("id") == driver_id:
                return load.get("delivery", {}).get("appointment")
        return None

    async def get_performance(
        self, driver_id: UUID, time_range: TimeRange
    ) -> PerformanceSnapshot:
        # Benign defaults in mock mode so no hard `extended_idle` rule trips
        # accidentally. Miguel's staged state uses `oor_miles=2.3` — well under
        # the 20-mile hard rule — so the anomaly agent (not rules) decides.
        return PerformanceSnapshot(
            driver_id=driver_id,
            oor_miles=2.3 if _is_miguel(driver_id) else 0.0,
            schedule_miles=500.0,
            actual_miles=512.5,
            schedule_time_minutes=480,
            actual_time_minutes=495,
            time_range=time_range,
        )

    async def get_trip_route(self, trip_id: UUID) -> TripRoute:
        # NavPro v1.0 doesn't expose trip route polylines; mock returns empty.
        return TripRoute(polyline="", planned_eta=_now_iso())

    async def find_nearby_places(
        self,
        lat: float,
        lng: float,
        place_type: PlaceType,
        radius_miles: float = 25,
    ) -> list[ParkingSpot]:
        if place_type != "parking":
            return []
        raw = self._load("tp_parking_poi.json")
        spots = [ParkingSpot.model_validate(p) for p in raw]
        # Naive distance filter — mock mode doesn't need haversine precision;
        # just return the seed set sorted by the seed's `distance_miles`.
        return sorted(spots, key=lambda s: s.distance_miles)[:8]

    # -- writes --

    async def create_trip(self, trip: TripUpsert) -> dict:
        # No-op in mock mode; return a synthetic trip_id.
        return {"trip_id": f"mock-{trip.load_id[:8]}"}

    async def assign_trip(self, trip_id: UUID, driver_id: UUID) -> None:
        return None


def _is_miguel(driver_id: UUID) -> bool:
    # Miguel Rodriguez is the anomaly-beat target — his seeded id anchors the
    # Block 4 demo arc. Keep stable across changes.
    return driver_id.endswith("-000000000002") or driver_id == "miguel"
