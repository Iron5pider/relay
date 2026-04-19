"""`NavProAdapter` ABC.

The seam between Relay's canonical domain and one upstream fleet-data source.
All concrete implementations (`MockTPAdapter`, `NavProHTTPAdapter`,
`SamsaraAdapter`) satisfy this contract. Routes and services only ever depend
on the ABC.

**Scope reconciliation (2026-04-19) against the real NavPro v1.0 API.**
`API_DOCS/NavPro_integration.md` §9 documents gaps where NavPro does not
provide what Notion API Models §4.3 speculatively expected. This ABC reflects
the real pull-only, no-HOS, no-push-webhooks, no-messaging surface:

- **Dropped from the ABC** (not on NavPro v1.0): `get_hos()`,
  `send_driver_message()`, `start_webhook_listener()`. HOS is Relay-tracked
  (self-reported via F6b post-call writeback). Driver messaging is voice-first
  via Twilio. No push webhooks — the exception engine polls.
- **Added**: `get_performance()` — powers the `oor_miles` / schedule-drift hard
  rules and feeds the anomaly agent's off-route signal.
- **Kept**: `list_drivers`, `get_location`, `get_breadcrumbs`, `get_trip_route`,
  `find_nearby_places`, `create_trip`, `assign_trip`. See NavPro_integration
  §8 translation tables for each.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Optional

from backend.models.schemas import Driver, ISODateTime, ParkingSpot, UUID


PlaceType = Literal["parking", "fuel", "weigh", "rest_area", "repair"]


@dataclass
class HosClocks:
    """Relay-tracked HOS snapshot. NavPro v1.0 doesn't expose these — the
    values come from seeds + F6b post-call writeback (driver self-report)."""

    drive_remaining_minutes: int
    shift_remaining_minutes: int
    cycle_remaining_minutes: int
    status: str  # matches `DriverStatus` values
    last_duty_change_at: ISODateTime
    next_mandatory_break_minutes: Optional[int] = None


@dataclass
class LocationPing:
    lat: float
    lng: float
    speed_mph: float
    heading_deg: Optional[float]
    recorded_at: ISODateTime


@dataclass
class TripRoute:
    polyline: str
    planned_eta: ISODateTime


@dataclass
class TimeRange:
    start_iso_utc: ISODateTime
    end_iso_utc: ISODateTime


@dataclass
class PerformanceSnapshot:
    """Output of `get_performance`. Populated from NavPro
    `/api/driver/performance/query` response when live; seeds simulate these
    for mock mode. See `API_DOCS/NavPro_integration.md` §5.§0 + §8."""

    driver_id: UUID
    oor_miles: Optional[float]
    schedule_miles: Optional[float]
    actual_miles: Optional[float]
    schedule_time_minutes: Optional[int]
    actual_time_minutes: Optional[int]
    time_range: TimeRange


@dataclass
class TripUpsert:
    load_id: UUID
    driver_id: UUID
    scheduled_start_time: ISODateTime
    stop_points: list[dict]  # list of {lat, lng, address_name, appointment_time, dwell_time, notes}


class NavProAdapter(ABC):
    """Every upstream fleet-data source implements this interface."""

    # -- reads --

    @abstractmethod
    async def list_drivers(self) -> list[Driver]:
        """All drivers in the carrier account. Canonical Relay `Driver` shape."""

    @abstractmethod
    async def get_location(self, driver_id: UUID) -> LocationPing:
        """Latest driver location. Maps from NavPro
        `POST /api/tracking/get/driver-dispatch` trail tail."""

    @abstractmethod
    async def get_breadcrumbs(
        self, driver_id: UUID, time_range: TimeRange
    ) -> list[LocationPing]:
        """GPS trail inside a time range (NavPro max 30 days per call)."""

    @abstractmethod
    async def get_active_trip_eta(self, driver_id: UUID) -> Optional[ISODateTime]:
        """`active_trip.eta` from the tracking endpoint, or None if no active trip.
        Critical for the ETA-drift hard rule + the anomaly agent's 'missing active_trip
        when a load is assigned' soft signal."""

    @abstractmethod
    async def get_performance(
        self, driver_id: UUID, time_range: TimeRange
    ) -> PerformanceSnapshot:
        """Per-driver mileage + time drift for the window.
        Feeds `oor_miles ≥ 20` hard rule and `schedule_actual_time_ratio` soft signal."""

    @abstractmethod
    async def get_trip_route(self, trip_id: UUID) -> TripRoute:
        """Planned polyline + ETA for a trip. Currently stubbed — NavPro v1.0
        doesn't expose a per-trip route endpoint; see NavPro_integration §9."""

    @abstractmethod
    async def find_nearby_places(
        self,
        lat: float,
        lng: float,
        place_type: PlaceType,
        radius_miles: float = 25,
    ) -> list[ParkingSpot]:
        """Trucker Path POI lookup. NavPro `/api/poi/*` returns company-custom only,
        so parking leans on `data/tp_parking_poi.json` static snapshot."""

    # -- writes --

    @abstractmethod
    async def create_trip(self, trip: TripUpsert) -> dict:
        """`POST /api/trip/create` with an idempotency key. Returns
        `{"trip_id": str}` per NavPro v1.0."""

    @abstractmethod
    async def assign_trip(self, trip_id: UUID, driver_id: UUID) -> None:
        """No-op on NavPro v1.0 (assignment is part of create_trip). Kept on
        the ABC for forward compatibility with NavPro v2 and `SamsaraAdapter`."""


__all__ = [
    "HosClocks",
    "LocationPing",
    "NavProAdapter",
    "PerformanceSnapshot",
    "PlaceType",
    "TimeRange",
    "TripRoute",
    "TripUpsert",
]
