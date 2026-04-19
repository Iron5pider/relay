"""Detention-invoice generation (PDF stubbed for now).

Looks up the call + load + detention_event + broker, computes the dollar amount
with Decimal math, inserts an `invoices` row with `pdf_url='pending'`, and
returns the id. Supabase Realtime auto-emits the INSERT on the `invoices`
channel so the dashboard can pick it up without any publisher code.

Real PDF rendering (via `@react-pdf/renderer` on the Next.js side or `pdfkit`
server-side) ships in Block 3. See `API_DOCS/tools_contract.md` §8.1.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import DetentionEvent, Invoice, Load, VoiceCall

logger = logging.getLogger("relay.detention")


async def generate_detention_invoice(db: AsyncSession, call_id: str) -> dict[str, Any]:
    """Create an `invoices` row for the detention call. Returns `{invoice_id, pdf_url, amount, status}`.

    `call_id` is the `voice_calls.id` (primary key) — not the ElevenLabs
    `conversation_id`. Callers that only have the conversation_id should
    resolve via `voice_calls.conversation_id` first.
    """
    call = await db.get(VoiceCall, call_id)
    if call is None:
        raise ValueError(f"voice_call {call_id!r} not found")
    if call.load_id is None:
        raise ValueError(f"voice_call {call_id!r} has no load_id")

    load = await db.get(Load, call.load_id)
    if load is None:
        raise ValueError(f"load {call.load_id!r} not found")

    # Pull the most recent COMMITTED detention_event for this call.
    # Refusals (committed_to_pay=False) never generate an invoice.
    ev_result = await db.execute(
        select(DetentionEvent)
        .where(
            DetentionEvent.call_id == call_id,
            DetentionEvent.committed_to_pay.is_(True),
        )
        .order_by(DetentionEvent.created_at.desc())
    )
    event = ev_result.scalars().first()
    if event is None:
        raise ValueError(
            f"no committed detention_event found for call {call_id!r} — "
            f"invoice generation requires confirm_detention with committed_to_pay=true"
        )

    # Amount = hours_confirmed * rate_per_hour. Decimal math, 2-dp.
    hours = event.detention_hours_confirmed or Decimal("0")
    rate = Decimal(load.detention_rate_per_hour)
    amount = (Decimal(hours) * rate).quantize(Decimal("0.01"))
    if amount < 0:
        amount = Decimal("0.00")

    invoice_id = str(uuid.uuid4())
    inv = Invoice(
        id=invoice_id,
        load_id=load.id,
        call_id=call.id,
        pdf_url="pending",  # Block 3 renders the real PDF
        amount=amount,
        status="ready_for_review",
    )
    db.add(inv)
    await db.commit()

    logger.info(
        "event=invoice_generated invoice_id=%s load=%s call=%s amount=%s",
        invoice_id,
        load.load_number,
        call.id,
        amount,
    )
    return {
        "invoice_id": invoice_id,
        "load_id": load.id,
        "pdf_url": "pending",
        "amount": float(amount),
        "status": "ready_for_review",
    }


__all__ = ["generate_detention_invoice"]
