"""Seed `data/*.json` into Postgres on first boot.

Rules (`backend/CLAUDE.md` §8 + §13):
- Only runs when `drivers` table is empty.
- Startup-gated on `settings.environment in {"local", "demo"}`.
- CLI (`python -m backend.db.seed`) runs unconditionally — explicit intent.
- `_demo_notes` strings on seed JSON are ignored (Pydantic `extra="ignore"` +
  manual mapping in `_row_*` functions below).
- Loads in FK order: brokers → drivers → loads.

The seed JSON for `loads` nests `driver` / `broker` Lite objects; this
module flattens them to `driver_id` / `broker_id` columns and lifts the
nested `pickup` / `delivery` stops into flat `pickup_*` / `delivery_*` cols.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db import session as db_session
from backend.models.db import Broker, Driver, Load

logger = logging.getLogger("relay.seed")

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _parse_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_json(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / name
    if not path.exists():
        logger.warning("event=seed_missing_json file=%s", path)
        return []
    return json.loads(path.read_text())


def _row_broker(data: dict[str, Any]) -> Broker:
    return Broker(
        id=data["id"],
        name=data["name"],
        contact_name=data["contact_name"],
        phone=data["phone"],
        email=data["email"],
        preferred_update_channel=data["preferred_update_channel"],
    )


def _row_driver(data: dict[str, Any]) -> Driver:
    return Driver(
        id=data["id"],
        name=data["name"],
        phone=data["phone"],
        preferred_language=data["preferred_language"],
        truck_number=data["truck_number"],
        current_lat=data.get("current_lat"),
        current_lng=data.get("current_lng"),
        hos_drive_remaining_minutes=data["hos_drive_remaining_minutes"],
        hos_shift_remaining_minutes=data["hos_shift_remaining_minutes"],
        hos_cycle_remaining_minutes=data["hos_cycle_remaining_minutes"],
        hos_remaining_minutes=data["hos_remaining_minutes"],
        status=data["status"],
        fatigue_level=data.get("fatigue_level", "unknown"),
        last_checkin_at=_parse_iso(data.get("last_checkin_at")),
        next_scheduled_checkin_at=_parse_iso(data.get("next_scheduled_checkin_at")),
        updated_at=_parse_iso(data["updated_at"]),
    )


def _row_load(data: dict[str, Any]) -> Load:
    pickup = data["pickup"]
    delivery = data["delivery"]
    driver_obj = data.get("driver")
    return Load(
        id=data["id"],
        load_number=data["load_number"],
        driver_id=driver_obj["id"] if driver_obj else None,
        broker_id=data["broker"]["id"],
        pickup_name=pickup["name"],
        pickup_lat=pickup["lat"],
        pickup_lng=pickup["lng"],
        pickup_phone=pickup.get("phone"),
        pickup_appointment=_parse_iso(pickup["appointment"]),
        delivery_name=delivery["name"],
        delivery_lat=delivery["lat"],
        delivery_lng=delivery["lng"],
        delivery_phone=delivery.get("phone"),
        delivery_appointment=_parse_iso(delivery["appointment"]),
        rate_linehaul=Decimal(str(data["rate_linehaul"])),
        detention_rate_per_hour=Decimal(str(data["detention_rate_per_hour"])),
        detention_free_minutes=data["detention_free_minutes"],
        status=data["status"],
        arrived_at_stop_at=_parse_iso(data.get("arrived_at_stop_at")),
        detention_minutes_elapsed=data.get("detention_minutes_elapsed", 0),
        exception_flags=data.get("exception_flags", []),
        created_at=_parse_iso(data["created_at"]),
        updated_at=_parse_iso(data.get("updated_at") or data["created_at"]),
    )


async def _count_drivers(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(Driver))
    return int(result.scalar_one())


async def _do_seed(session: AsyncSession) -> tuple[int, int, int]:
    brokers = [_row_broker(b) for b in _load_json("brokers.json")]
    drivers = [_row_driver(d) for d in _load_json("drivers.json")]
    loads = [_row_load(load) for load in _load_json("loads.json")]

    session.add_all(brokers)
    await session.flush()
    session.add_all(drivers)
    await session.flush()
    session.add_all(loads)
    await session.commit()

    return len(brokers), len(drivers), len(loads)


async def seed_if_empty(session: AsyncSession, *, force: bool = False) -> bool:
    """Run the seed if the drivers table is empty. Returns True if seeding ran."""
    if not force:
        count = await _count_drivers(session)
        if count > 0:
            logger.info("event=seed_skip reason=drivers_exists count=%d", count)
            return False

    brokers, drivers, loads = await _do_seed(session)
    logger.info(
        "event=seed_complete brokers=%d drivers=%d loads=%d",
        brokers,
        drivers,
        loads,
    )
    return True


async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    db_session.get_engine()
    factory = db_session.AsyncSessionLocal
    assert factory is not None
    async with factory() as session:
        ran = await seed_if_empty(session, force=False)
    await db_session.dispose_engine()
    if ran:
        print("seed_complete")
    else:
        print("seed_skipped (table already populated)")


if __name__ == "__main__":
    asyncio.run(_main())


__all__ = ["seed_if_empty"]
