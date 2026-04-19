"""NavProPoller — composes adapter reads into one `NavProSnapshot`.

Fans out `get_adapter().list_drivers()` (identity + `latest_update`),
`get_adapter().get_location()` / `get_breadcrumbs()` (GPS trail freshness),
`get_adapter().get_active_trip_eta()` (active trip presence), and
`get_adapter().get_performance()` (off-route + schedule drift) via
`asyncio.gather(..., return_exceptions=True)`. Per-endpoint failures become
`snap.*_ok = False` + `degraded_reason` rather than raising — so the scheduler
tick never crashes on a single NavPro 5xx.

Translations follow `API_DOCS/NavPro_integration.md` §8 verbatim. No invented
logic here — if a field name or unit looks off, reconcile against the guide.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from backend.models.schemas import Driver, ISODateTime, UUID

from .adapters import get_adapter
from .adapters.base import LocationPing, PerformanceSnapshot, TimeRange
from .anomaly_agent_schemas import NavProSnapshot

logger = logging.getLogger("relay.navpro_poller")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_to_dt(iso: Optional[str]) -> Optional[datetime]:
    if iso is None:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _minutes_since(iso: Optional[str]) -> Optional[int]:
    dt = _iso_to_dt(iso)
    if dt is None:
        return None
    delta = datetime.now(timezone.utc) - dt
    return max(int(delta.total_seconds() // 60), 0)


def _driver_by_id(drivers: list[Driver], driver_id: UUID) -> Optional[Driver]:
    return next((d for d in drivers if d.id == driver_id), None)


async def collect_snapshot(
    driver_id: UUID,
    breadcrumb_lookback_minutes: int = 60,
) -> NavProSnapshot:
    """Produce one tick's NavProSnapshot. Never raises — endpoint failures
    surface via per-endpoint `*_ok` flags + `degraded_reason`."""
    import asyncio

    adapter = get_adapter()
    now_dt = datetime.now(timezone.utc)
    tr = TimeRange(
        start_iso_utc=(
            now_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        ),
        end_iso_utc=now_dt.isoformat().replace("+00:00", "Z"),
    )

    driver_task = adapter.list_drivers()
    location_task = adapter.get_location(driver_id)
    breadcrumbs_task = adapter.get_breadcrumbs(driver_id, tr)
    active_trip_task = adapter.get_active_trip_eta(driver_id)
    performance_task = adapter.get_performance(driver_id, tr)

    results = await asyncio.gather(
        driver_task,
        location_task,
        breadcrumbs_task,
        active_trip_task,
        performance_task,
        return_exceptions=True,
    )

    drivers_raw, location_raw, trail_raw, eta_raw, performance_raw = results

    snap = NavProSnapshot(
        driver_id=driver_id,
        fetched_at_utc=_now_utc_iso(),
    )

    # --- /api/driver/query slot ---
    degraded_parts: list[str] = []
    if isinstance(drivers_raw, Exception):
        snap.driver_query_ok = False
        degraded_parts.append(f"list_drivers:{type(drivers_raw).__name__}")
    else:
        driver = _driver_by_id(drivers_raw, driver_id)
        if driver is not None:
            snap.last_known_lat = driver.current_lat
            snap.last_known_lng = driver.current_lng
            snap.latest_update_utc = driver.updated_at
            snap.tracking_stale_minutes = _minutes_since(driver.updated_at)
            # We don't have NavPro's raw `work_status` in the canonical
            # Driver — fall back to canonical status for now; a future
            # iteration can carry the raw string through.
            snap.work_status = driver.status.value

    # --- /api/tracking/get/driver-dispatch slot ---
    if isinstance(location_raw, Exception):
        snap.tracking_ok = False
        degraded_parts.append(f"get_location:{type(location_raw).__name__}")
    else:
        ping: LocationPing = location_raw  # type: ignore[assignment]
        if snap.last_known_lat is None:
            snap.last_known_lat = ping.lat
            snap.last_known_lng = ping.lng
        if snap.latest_update_utc is None:
            snap.latest_update_utc = ping.recorded_at
            snap.tracking_stale_minutes = _minutes_since(ping.recorded_at)

    if isinstance(trail_raw, Exception):
        snap.tracking_ok = False
        degraded_parts.append(f"get_breadcrumbs:{type(trail_raw).__name__}")
    else:
        trail: list[LocationPing] = trail_raw  # type: ignore[assignment]
        snap.trail_last_1h_points = len(trail)
        if trail:
            tail = trail[-1]
            snap.last_trail_point = {
                "lat": tail.lat,
                "lng": tail.lng,
                "recorded_at": tail.recorded_at,
                "speed_mph": tail.speed_mph,
            }

    if isinstance(eta_raw, Exception):
        snap.tracking_ok = False
        degraded_parts.append(f"get_active_trip_eta:{type(eta_raw).__name__}")
    else:
        snap.active_trip_eta_utc = eta_raw  # type: ignore[assignment]

    # --- /api/driver/performance/query slot ---
    if isinstance(performance_raw, Exception):
        snap.performance_ok = False
        degraded_parts.append(f"get_performance:{type(performance_raw).__name__}")
    else:
        perf: PerformanceSnapshot = performance_raw  # type: ignore[assignment]
        snap.oor_miles_last_24h = perf.oor_miles
        snap.schedule_miles = perf.schedule_miles
        snap.actual_miles = perf.actual_miles
        if perf.schedule_time_minutes and perf.actual_time_minutes:
            snap.schedule_actual_time_ratio = (
                perf.actual_time_minutes / perf.schedule_time_minutes
            )

    if degraded_parts:
        snap.degraded_reason = ";".join(degraded_parts)
        logger.info(
            "event=navpro_snapshot_degraded driver_id=%s reason=%s",
            driver_id,
            snap.degraded_reason,
        )

    return snap


__all__ = ["collect_snapshot"]
