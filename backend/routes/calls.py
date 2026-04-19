"""`POST /internal/call/initiate` — fire one outbound call.

Looks up driver + load from seeds, assembles dynamic_variables per the
agent_kind, delegates to `services.call_orchestrator.place_outbound_call`.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_db
from backend.models.db import Broker, Driver, Load
from backend.models.tool_schemas import CallInitiateRequest
from backend.services.auth import require_relay_token
from backend.services.call_orchestrator import place_outbound_call
from backend.services.envelope import EnvelopeError, ok

logger = logging.getLogger("relay.routes.calls")

router = APIRouter(dependencies=[Depends(require_relay_token)])


@router.post("/call/initiate")
async def initiate_call(
    body: CallInitiateRequest, db: AsyncSession = Depends(get_db)
):
    driver: Driver | None = None
    load: Load | None = None
    if body.driver_id:
        driver = await db.get(Driver, body.driver_id)
        if driver is None:
            raise EnvelopeError(
                "driver_not_found", "No driver found for that ID.", http_status=404
            )
    if body.load_id:
        load = await db.get(Load, body.load_id)
        if load is None:
            raise EnvelopeError(
                "load_not_found", "No load found for that ID.", http_status=404
            )

    # Derive to_number: explicit > driver.phone > load.delivery_phone > broker.phone
    to_number = body.to_number
    if not to_number and driver and body.agent_kind == "driver_agent":
        to_number = driver.phone
    if not to_number and load and body.agent_kind == "detention_agent":
        to_number = load.delivery_phone
    if not to_number and load and body.agent_kind == "broker_update_agent":
        broker = await db.get(Broker, load.broker_id)
        if broker:
            to_number = broker.phone
    if not to_number:
        raise EnvelopeError(
            "missing_to_number",
            "Cannot resolve to_number from the request context.",
            http_status=400,
        )

    # Build dynamic_variables per agent_kind.
    dv: dict[str, Any] = dict(body.extra_dynamic_variables or {})
    dv["agent_kind"] = body.agent_kind
    dv["trigger_reason"] = body.trigger_reason.value

    if driver:
        dv["driver_id"] = driver.id
        dv["driver_name"] = driver.name
        dv["driver_first_name"] = driver.name.split(" ", 1)[0] if driver.name else ""
        dv["truck_number"] = driver.truck_number
        dv["preferred_language"] = driver.preferred_language
        dv["hos_drive_remaining_minutes"] = driver.hos_drive_remaining_minutes
        dv["fatigue_level_last_known"] = driver.fatigue_level
    if load:
        dv["current_load_id"] = load.id
        dv["load_number"] = load.load_number
        dv["pickup_name"] = load.pickup_name
        dv["delivery_name"] = load.delivery_name
        dv["detention_rate_per_hour"] = float(load.detention_rate_per_hour)
        dv["detention_free_minutes"] = load.detention_free_minutes

    language = driver.preferred_language if driver else "en"

    voice_call_id, call_sid, conversation_id = await place_outbound_call(
        db=db,
        agent_kind=body.agent_kind,
        to_number=to_number,
        dynamic_variables=dv,
        first_message_override=body.first_message_override,
        driver_id=driver.id if driver else None,
        load_id=load.id if load else None,
        trigger_reason=body.trigger_reason.value,
        language=language,
    )

    # Publish call.started so the dashboard shows the call immediately.
    from backend.bus.channels import dispatcher_channel
    from backend.bus.publisher import publish

    publish(dispatcher_channel(), "call.started", {
        "call_id": voice_call_id,
        "conversation_id": conversation_id,
        "agent_kind": body.agent_kind,
        "to_number": to_number,
        "driver_id": driver.id if driver else None,
        "load_id": load.id if load else None,
    })

    return ok(
        {
            "conversation_id": conversation_id,
            "call_sid": call_sid,
            "voice_call_id": voice_call_id,
        }
    )


__all__ = ["router"]
