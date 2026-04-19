"""Personalization webhook builder — driver-by-caller-id lookup.

Used by `/webhooks/elevenlabs/personalization` to respond within ~3s with
dynamic_variables + first_message_override per `tools_contract.md` §7. When
the caller isn't in our drivers table we return a minimal English fallback
so the agent can still ground.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.db import Driver, Load


def _first_name(full_name: str) -> str:
    return full_name.strip().split(" ", 1)[0] if full_name else ""


async def resolve_inbound_caller(
    db: AsyncSession, caller_id: str, called_number: str | None = None
) -> dict[str, Any]:
    """Look up driver by E.164 phone number; return a personalization payload.

    Always returns the `{dynamic_variables, first_message_override}` shape.
    """
    result = await db.execute(select(Driver).where(Driver.phone == caller_id))
    driver: Driver | None = result.scalar_one_or_none()

    if driver is None:
        return {
            "dynamic_variables": {
                "caller_id": caller_id,
                "trigger_reason": "inbound",
                "preferred_language": "en",
                "driver_first_name": "driver",
                "driver_name": "driver",
                "truck_number": "unknown",
                "hos_drive_remaining_minutes": "",
                "fatigue_level_last_known": "unknown",
                "current_load_id": "",
                "current_lat": None,
                "current_lng": None,
                "last_gps_city": None,
                "secret__relay_token": settings.relay_internal_token,
                "voice_call_id": str(uuid.uuid4()),
            },
            "first_message_override": (
                "Radar dispatch, this is Maya — who am I speaking with?"
            ),
        }

    # Active load for this driver (if any).
    load_result = await db.execute(
        select(Load).where(Load.driver_id == driver.id).order_by(Load.created_at.desc())
    )
    load = load_result.scalars().first()

    first_name = _first_name(driver.name)
    dv: dict[str, Any] = {
        "driver_id": driver.id,
        "driver_name": first_name,
        "driver_first_name": first_name,
        "truck_number": driver.truck_number,
        "preferred_language": driver.preferred_language,
        "trigger_reason": "inbound",
        "hos_drive_remaining_minutes": driver.hos_drive_remaining_minutes,
        "fatigue_level_last_known": driver.fatigue_level,
        "current_load_id": load.id if load else None,
        "current_lat": driver.current_lat,
        "current_lng": driver.current_lng,
        "last_gps_city": None,  # Block 2 adds reverse geocoding
        "secret__relay_token": settings.relay_internal_token,
        "voice_call_id": str(uuid.uuid4()),
    }

    greetings = {
        "en": f"Radar dispatch, this is Maya — hi {first_name}, what's up?",
        "es": f"Hola {first_name}, soy Maya de Radar — ¿qué tal?",
        "pa": f"Sat Sri Akal {first_name}, main Maya haan — ki haal hai?",
    }
    first_message = greetings.get(driver.preferred_language, greetings["en"])

    return {"dynamic_variables": dv, "first_message_override": first_message}


__all__ = ["resolve_inbound_caller"]
