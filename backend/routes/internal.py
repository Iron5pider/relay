"""Internal automation endpoints.

- `POST /internal/invoice/generate_detention` — called by the post_call webhook
  background task (and by tests). Writes an `invoices` row (PDF stubbed).
- `POST /internal/dispatcher/urgent_queue` — creates a high-priority
  `dispatcher_tasks` row from a call_id.

Both are Bearer-protected so local callers pass the Relay token same as tools.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_db
from backend.models.db import DispatcherTask, VoiceCall
from backend.models.tool_schemas import CallIdBody
from backend.services.auth import require_relay_token
from backend.services.detention import generate_detention_invoice
from backend.services.envelope import EnvelopeError, ok

logger = logging.getLogger("relay.internal")

router = APIRouter(dependencies=[Depends(require_relay_token)])


@router.post("/invoice/generate_detention")
async def generate_invoice_endpoint(
    body: CallIdBody, db: AsyncSession = Depends(get_db)
):
    # Resolve call_id — accept either voice_calls.id or conversation_id.
    call = await db.get(VoiceCall, body.call_id)
    if call is None:
        # Try conversation_id lookup.
        from sqlalchemy import select

        r = await db.execute(
            select(VoiceCall).where(VoiceCall.conversation_id == body.call_id)
        )
        call = r.scalar_one_or_none()
    if call is None:
        raise EnvelopeError(
            "call_not_found", "No call found for that ID.", http_status=404
        )

    result = await generate_detention_invoice(db, call.id)
    return ok(result)


@router.post("/dispatcher/urgent_queue")
async def urgent_queue_endpoint(
    body: CallIdBody, db: AsyncSession = Depends(get_db)
):
    call = await db.get(VoiceCall, body.call_id)
    if call is None:
        from sqlalchemy import select

        r = await db.execute(
            select(VoiceCall).where(VoiceCall.conversation_id == body.call_id)
        )
        call = r.scalar_one_or_none()
    if call is None:
        raise EnvelopeError(
            "call_not_found", "No call found for that ID.", http_status=404
        )

    summary = (call.analysis_json or {}).get("transcript_summary") or "Driver issue flagged"
    task_id = str(uuid.uuid4())
    db.add(
        DispatcherTask(
            id=task_id,
            priority="high",
            title=f"Urgent — review call {call.id[:8]}",
            body=summary[:1000],
            related_call_id=call.id,
        )
    )
    await db.commit()
    logger.info("event=urgent_task_created task_id=%s call_id=%s", task_id, call.id)
    return ok({"task_id": task_id})


@router.post("/batch-broker-updates")
async def batch_broker_updates(
    body: dict, db: AsyncSession = Depends(get_db)
):
    """Fan out broker update calls concurrently.

    Request: { broker_ids: list[str] | null, update_type: str }
    If broker_ids is null, calls all brokers on active loads.
    """
    import asyncio

    from sqlalchemy import select

    from backend.config import settings
    from backend.models.db import Broker, Load
    from backend.services.call_orchestrator import place_outbound_call

    broker_ids = body.get("broker_ids")
    update_type = body.get("update_type", "end_of_day")

    # Find brokers + their active loads.
    if broker_ids:
        brokers_q = await db.execute(select(Broker).where(Broker.id.in_(broker_ids)))
    else:
        # All brokers with active loads.
        active_loads_q = await db.execute(
            select(Load).where(Load.status.in_(["in_transit", "at_pickup", "at_delivery"]))
        )
        active_loads = list(active_loads_q.scalars().all())
        broker_id_set = {l.broker_id for l in active_loads}
        if not broker_id_set:
            return ok({"batch_id": str(uuid.uuid4()), "call_ids": [], "count": 0})
        brokers_q = await db.execute(select(Broker).where(Broker.id.in_(broker_id_set)))

    brokers = list(brokers_q.scalars().all())
    if not brokers:
        return ok({"batch_id": str(uuid.uuid4()), "call_ids": [], "count": 0})

    batch_id = str(uuid.uuid4())
    sem = asyncio.Semaphore(settings.batch_calls_max_concurrency)
    call_ids: list[str] = []

    async def _call_broker(broker: Broker) -> str | None:
        async with sem:
            # Find this broker's active load.
            load_q = await db.execute(
                select(Load).where(
                    Load.broker_id == broker.id,
                    Load.status.in_(["in_transit", "at_pickup", "at_delivery"]),
                ).order_by(Load.created_at.desc())
            )
            load = load_q.scalars().first()
            if load is None:
                return None

            dv = {
                "agent_kind": "broker_update_agent",
                "trigger_reason": update_type,
                "load_number": load.load_number,
                "load_id": load.id,
                "broker_rep_first_name": broker.contact_name.split(" ", 1)[0],
                "broker_name": broker.name,
            }
            try:
                vid, _, _ = await place_outbound_call(
                    db=db,
                    agent_kind="broker_update_agent",
                    to_number=broker.phone,
                    dynamic_variables=dv,
                    driver_id=load.driver_id,
                    load_id=load.id,
                    trigger_reason=update_type,
                )
                return vid
            except Exception:
                logger.exception("event=batch_broker_call_failed broker=%s", broker.id)
                return None

    results = await asyncio.gather(*[_call_broker(b) for b in brokers])
    call_ids = [r for r in results if r is not None]

    logger.info("event=batch_broker_updates batch_id=%s count=%d", batch_id, len(call_ids))
    return ok({"batch_id": batch_id, "call_ids": call_ids, "count": len(call_ids)})


__all__ = ["router"]
