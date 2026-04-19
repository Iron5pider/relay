"""NavProHTTPAdapter — real httpx client against `api.truckerpath.com/navpro`.

Endpoint + translation contract lives in `API_DOCS/NavPro_integration.md`.
This module implements §8 translations exactly; no invented logic. Token-bucket
throttle at 20 QPS (internal ceiling under the 25 QPS documented cap).

**Hackathon scoping note.** Block 1.5 lands the JWT + httpx wiring live.
Until then, the methods return `NotImplementedError` with a pointer to the
integration guide so callers don't silently misbehave. The ABC shape is stable
so `RELAY_ADAPTER=mock` remains the demo default.
"""

from __future__ import annotations

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

_STUB_MSG = (
    "NavPro live adapter lands in Block 1.5. See "
    "`API_DOCS/NavPro_integration.md` §4 (auth), §5 (endpoints), §8 (translations)."
)


class NavProHTTPAdapter(NavProAdapter):
    async def list_drivers(self) -> list[Driver]:
        raise NotImplementedError(_STUB_MSG)

    async def get_location(self, driver_id: UUID) -> LocationPing:
        raise NotImplementedError(_STUB_MSG)

    async def get_breadcrumbs(
        self, driver_id: UUID, time_range: TimeRange
    ) -> list[LocationPing]:
        raise NotImplementedError(_STUB_MSG)

    async def get_active_trip_eta(self, driver_id: UUID) -> Optional[ISODateTime]:
        raise NotImplementedError(_STUB_MSG)

    async def get_performance(
        self, driver_id: UUID, time_range: TimeRange
    ) -> PerformanceSnapshot:
        raise NotImplementedError(_STUB_MSG)

    async def get_trip_route(self, trip_id: UUID) -> TripRoute:
        raise NotImplementedError(_STUB_MSG)

    async def find_nearby_places(
        self,
        lat: float,
        lng: float,
        place_type: PlaceType,
        radius_miles: float = 25,
    ) -> list[ParkingSpot]:
        raise NotImplementedError(_STUB_MSG)

    async def create_trip(self, trip: TripUpsert) -> dict:
        raise NotImplementedError(_STUB_MSG)

    async def assign_trip(self, trip_id: UUID, driver_id: UUID) -> None:
        raise NotImplementedError(_STUB_MSG)
