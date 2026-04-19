"""ElevenLabs webhook receivers.

- `POST /webhooks/elevenlabs/post_call` — HMAC-verified, idempotent on
  conversation_id. UPSERTs the `voice_calls` row, then branches on agent_id
  per `tools_contract.md` §6.3.
- `POST /webhooks/elevenlabs/personalization` — fires during Twilio ringback;
  returns `{dynamic_variables, first_message_override}` RAW (no envelope).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.deps import get_db
from backend.models.db import Load, VoiceCall, WebhookEvent
from backend.models.tool_schemas import PersonalizationRequest
from backend.services.envelope import ok
from backend.services.personalization import resolve_inbound_caller
from backend.services.signatures import verify_elevenlabs_signature

logger = logging.getLogger("relay.webhooks.elevenlabs")

router = APIRouter()


def _iso_z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _parse_iso(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except ValueError:
        return None


def _map_status(raw: str) -> str:
    raw = (raw or "").lower()
    return {
        "done": "done",
        "complete": "done",
        "completed": "done",
        "success": "done",
        "voicemail": "voicemail",
        "no_answer": "no_answer",
        "no-answer": "no_answer",
        "failed": "failed",
        "in-progress": "in_progress",
        "in_progress": "in_progress",
    }.get(raw, "done")


@router.post("/post_call")
async def post_call(
    request: Request,
    background: BackgroundTasks,
    elevenlabs_signature: str | None = Header(default=None, alias="ElevenLabs-Signature"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    raw_body = await request.body()

    # HMAC verify first.
    if settings.elevenlabs_webhook_secret:
        if not verify_elevenlabs_signature(
            raw_body, elevenlabs_signature, settings.elevenlabs_webhook_secret
        ):
            logger.warning("event=elevenlabs_post_call_sig_fail")
            raise HTTPException(status_code=403, detail="invalid_signature")
    else:
        logger.warning("event=elevenlabs_post_call_sig_skipped reason=no_secret_configured")

    import orjson

    try:
        payload = orjson.loads(raw_body)
    except orjson.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid_json")

    data = payload.get("data") or {}
    conversation_id = data.get("conversation_id")
    if not conversation_id:
        raise HTTPException(status_code=400, detail="missing_conversation_id")

    # Idempotency via webhook_events unique(provider, provider_event_id).
    existing = await db.execute(
        select(WebhookEvent.id).where(
            WebhookEvent.provider == "elevenlabs",
            WebhookEvent.provider_event_id == conversation_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        logger.info("event=elevenlabs_post_call_duplicate conversation_id=%s", conversation_id)
        return ok({"duplicate": True})

    import uuid as _uuid
    db.add(
        WebhookEvent(
            id=str(_uuid.uuid4()),
            provider="elevenlabs",
            provider_event_id=conversation_id,
            body=payload,
            processed_at=datetime.now(timezone.utc),
        )
    )

    # UPSERT voice_calls by conversation_id.
    call_q = await db.execute(
        select(VoiceCall).where(VoiceCall.conversation_id == conversation_id)
    )
    vc: VoiceCall | None = call_q.scalar_one_or_none()

    # ElevenLabs echoes our dynamic_variables back in the post-call payload.
    # We use them to hydrate fields that weren't set when the row was created
    # (e.g. an inbound call that we didn't initiate ourselves).
    dyn_vars = (
        (data.get("conversation_initiation_client_data") or {}).get("dynamic_variables")
        or data.get("dynamic_variables")
        or {}
    )

    if vc is None:
        # Inbound call or out-of-band record; create a minimal row.
        vc_id = str(_uuid.uuid4())
        vc = VoiceCall(
            id=vc_id,
            conversation_id=conversation_id,
            agent_id=data.get("agent_id"),
            direction=(data.get("metadata", {}).get("phone_call", {}) or {}).get("direction", "inbound"),
            purpose="other",
            from_number=(data.get("metadata", {}).get("phone_call", {}) or {}).get("from_number", ""),
            to_number=(data.get("metadata", {}).get("phone_call", {}) or {}).get("to_number", ""),
            language=str(dyn_vars.get("preferred_language") or "en"),
            started_at=datetime.now(timezone.utc),
            twilio_call_sid=data.get("twilio_call_sid", "unknown"),
            outcome="in_progress",
            call_status="dialing",
            driver_id=dyn_vars.get("driver_id"),
            load_id=dyn_vars.get("current_load_id") or dyn_vars.get("load_id"),
            trigger_reason=dyn_vars.get("trigger_reason"),
        )
        db.add(vc)
        await db.flush()
    else:
        # Row already exists (we initiated the call) — hydrate fields that
        # might be missing from the initial insert. Never overwrite non-null
        # values we already set.
        if vc.load_id is None:
            vc.load_id = dyn_vars.get("current_load_id") or dyn_vars.get("load_id")
        if vc.driver_id is None:
            vc.driver_id = dyn_vars.get("driver_id")
        if vc.trigger_reason is None:
            vc.trigger_reason = dyn_vars.get("trigger_reason")

    vc.transcript = data.get("transcript", [])
    vc.analysis_json = data.get("analysis", {}) or {}
    vc.structured_data_json = (data.get("analysis", {}) or {}).get(
        "data_collection_results", {}
    )
    vc.call_status = _map_status(data.get("status", "done"))
    vc.duration_seconds = int(data.get("call_duration_secs") or 0) or None

    started_at = _parse_iso(data.get("started_at"))
    ended_at = _parse_iso(data.get("ended_at")) or datetime.now(timezone.utc)
    if started_at:
        vc.started_at = started_at
    vc.ended_at = ended_at

    # Outcome mapping from analysis.call_successful
    call_successful = (data.get("analysis") or {}).get("call_successful", "")
    if call_successful == "success":
        vc.outcome = "resolved"
    elif call_successful == "failure":
        vc.outcome = "escalated"
    elif vc.call_status == "voicemail":
        vc.outcome = "voicemail"
    elif vc.call_status == "failed":
        vc.outcome = "failed"

    # Branch on agent_id (§6.3).
    agent_id = data.get("agent_id", "")
    dc = ((data.get("analysis") or {}).get("data_collection_results") or {})

    await db.commit()

    # Fan out side-effects as background tasks so the webhook acks quickly.
    if agent_id == settings.elevenlabs_agent_detention_id:
        committed = _extract_bool(dc.get("committed_to_pay"))
        if committed:
            background.add_task(_generate_invoice_async, vc.id)
    elif agent_id == settings.elevenlabs_agent_driver_id:
        issues_flagged = _extract_bool(dc.get("issues_flagged"))
        if issues_flagged:
            background.add_task(_urgent_queue_async, vc.id)
    # broker_update: no side-effect beyond voice_calls + dispatcher_notifications
    # already written by `mark_broker_updated` tool during the call.

    logger.info(
        "event=elevenlabs_post_call_verified conversation_id=%s agent=%s status=%s",
        conversation_id,
        agent_id,
        vc.call_status,
    )
    return ok({"processed": True})


def _extract_bool(field: Any) -> bool:
    """ElevenLabs data_collection_results entries are `{value, rationale}`.
    Accept either the raw value or the envelope."""
    if isinstance(field, dict):
        return bool(field.get("value"))
    return bool(field)


async def _generate_invoice_async(voice_call_id: str) -> None:
    # Lazy import to avoid circularity.
    from backend.db import session as db_session
    from backend.services.detention import generate_detention_invoice

    factory = db_session.AsyncSessionLocal
    if factory is None:
        db_session.get_engine()
        factory = db_session.AsyncSessionLocal
    assert factory is not None
    async with factory() as session:
        try:
            await generate_detention_invoice(session, voice_call_id)
        except Exception:
            logger.exception(
                "event=invoice_background_failed voice_call_id=%s", voice_call_id
            )


async def _urgent_queue_async(voice_call_id: str) -> None:
    import uuid as _uuid

    from backend.db import session as db_session
    from backend.models.db import DispatcherTask, VoiceCall

    factory = db_session.AsyncSessionLocal
    if factory is None:
        db_session.get_engine()
        factory = db_session.AsyncSessionLocal
    assert factory is not None
    async with factory() as session:
        call = await session.get(VoiceCall, voice_call_id)
        if call is None:
            return
        summary = (call.analysis_json or {}).get("transcript_summary") or "Driver issue flagged"
        session.add(
            DispatcherTask(
                id=str(_uuid.uuid4()),
                priority="high",
                title=f"Urgent — review call {voice_call_id[:8]}",
                body=summary[:1000],
                related_call_id=voice_call_id,
            )
        )
        await session.commit()


@router.post("/personalization")
async def personalization(
    body: PersonalizationRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    # Intentionally NO envelope — ElevenLabs expects `{dynamic_variables, first_message_override}`
    # at the top level per `tools_contract.md` §7.
    payload = await resolve_inbound_caller(db, body.caller_id, body.called_number)
    logger.info(
        "event=personalization_lookup caller_id=%s matched_driver=%s",
        body.caller_id,
        bool(payload["dynamic_variables"].get("driver_id")),
    )
    return payload


__all__ = ["router"]
