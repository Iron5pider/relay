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


__all__ = ["router"]
