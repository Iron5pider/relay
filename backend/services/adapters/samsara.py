"""SamsaraAdapter — optional Q&A sanity check against the public sandbox.

Not on the demo path. Compatibility map lives in Notion **API Models** §4.3.
Stubbed until someone actually exercises it.
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


class SamsaraAdapter(NavProAdapter):
    async def list_drivers(self) -> list[Driver]:
        raise NotImplementedError("SamsaraAdapter is Q&A-only; not on demo path.")

    async def get_location(self, driver_id: UUID) -> LocationPing:
        raise NotImplementedError("SamsaraAdapter is Q&A-only.")

    async def get_breadcrumbs(
        self, driver_id: UUID, time_range: TimeRange
    ) -> list[LocationPing]:
        raise NotImplementedError("SamsaraAdapter is Q&A-only.")

    async def get_active_trip_eta(self, driver_id: UUID) -> Optional[ISODateTime]:
        raise NotImplementedError("SamsaraAdapter is Q&A-only.")

    async def get_performance(
        self, driver_id: UUID, time_range: TimeRange
    ) -> PerformanceSnapshot:
        raise NotImplementedError("SamsaraAdapter is Q&A-only.")

    async def get_trip_route(self, trip_id: UUID) -> TripRoute:
        raise NotImplementedError("SamsaraAdapter is Q&A-only.")

    async def find_nearby_places(
        self,
        lat: float,
        lng: float,
        place_type: PlaceType,
        radius_miles: float = 25,
    ) -> list[ParkingSpot]:
        raise NotImplementedError("SamsaraAdapter is Q&A-only.")

    async def create_trip(self, trip: TripUpsert) -> dict:
        raise NotImplementedError("SamsaraAdapter is Q&A-only.")

    async def assign_trip(self, trip_id: UUID, driver_id: UUID) -> None:
        raise NotImplementedError("SamsaraAdapter is Q&A-only.")
