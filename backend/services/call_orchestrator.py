"""Outbound call orchestrator — fires calls via ElevenLabs' native Twilio integration.

Calls `POST https://api.elevenlabs.io/v1/convai/twilio/outbound-call` per
`API_DOCS/tools_contract.md` §5.1. Writes a `voice_calls` row with
`call_status='dialing'` BEFORE returning so the FE can subscribe to the row's
eventual updates via Supabase Realtime.

Never raises for "normal" failures (4xx/5xx from ElevenLabs) — returns the
error body so the caller can surface it through the envelope.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.db import VoiceCall
from backend.models.tool_schemas import AgentKind

logger = logging.getLogger("relay.call_orchestrator")

ELEVENLABS_OUTBOUND_URL = "https://api.elevenlabs.io/v1/convai/twilio/outbound-call"


def _agent_id_for(kind: AgentKind) -> str:
    mapping = {
        "driver_agent": settings.elevenlabs_agent_driver_checkin_id,
        "detention_agent": settings.elevenlabs_agent_detention_id,
        "broker_update_agent": settings.elevenlabs_agent_broker_id,
    }
    agent_id = mapping.get(kind, "")
    if not agent_id:
        raise RuntimeError(
            f"No ElevenLabs agent ID configured for kind={kind!r}. "
            f"Set the corresponding env var."
        )
    return agent_id


async def place_outbound_call(
    *,
    db: AsyncSession,
    agent_kind: AgentKind,
    to_number: str,
    dynamic_variables: dict[str, Any],
    first_message_override: str | None = None,
    driver_id: str | None = None,
    load_id: str | None = None,
    trigger_reason: str | None = None,
    language: str = "en",
) -> tuple[str, str | None, str]:
    """Place one outbound call. Returns `(voice_call_id, call_sid, conversation_id)`.

    Writes the `voice_calls` row pre-dial so Supabase Realtime sees the row
    before the ElevenLabs response lands. `conversation_id` is updated in the
    row as soon as the API responds. On failure, the row keeps `call_status='dialing'`
    for reconciliation (a future sweep can move stuck dialing rows to failed).
    """
    if not settings.elevenlabs_api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is empty; cannot place outbound call.")
    if not settings.elevenlabs_phone_number_id:
        raise RuntimeError(
            "ELEVENLABS_PHONE_NUMBER_ID is empty. Grab it from the ElevenLabs "
            "dashboard → Phone Numbers after connecting your Twilio account."
        )
    agent_id = _agent_id_for(agent_kind)

    voice_call_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    from_number = settings.twilio_from_number or "+10000000000"

    # 1. Pre-write the row so the FE can see 'dialing' state immediately.
    vc = VoiceCall(
        id=voice_call_id,
        load_id=load_id,
        driver_id=driver_id,
        agent_id=agent_id,
        direction="outbound",
        purpose=_purpose_for(agent_kind),
        from_number=from_number,
        to_number=to_number,
        language=language,
        started_at=now,
        outcome="in_progress",
        call_status="dialing",
        trigger_reason=trigger_reason,
        twilio_call_sid="pending",
    )
    db.add(vc)
    await db.commit()
    await db.refresh(vc)

    # 2. Build the ElevenLabs payload. Always inject the Bearer token
    #    (tools_contract §0 + §5.1) so the agent can auth tool calls.
    merged_vars: dict[str, Any] = {**dynamic_variables}
    if settings.relay_internal_token:
        merged_vars["secret__relay_token"] = settings.relay_internal_token
    # Per-call metadata so every tool call tracks back to this voice_calls row.
    merged_vars["voice_call_id"] = voice_call_id
    merged_vars.setdefault("trigger_reason", trigger_reason or "")

    payload: dict[str, Any] = {
        "agent_id": agent_id,
        "agent_phone_number_id": settings.elevenlabs_phone_number_id,
        "to_number": to_number,
        "conversation_initiation_client_data": {
            "dynamic_variables": merged_vars,
        },
    }
    if first_message_override:
        payload["conversation_initiation_client_data"][
            "conversation_config_override"
        ] = {"agent": {"first_message": first_message_override}}

    # 3. Fire the request.
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    conversation_id = ""
    call_sid: str | None = None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(ELEVENLABS_OUTBOUND_URL, json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()
        conversation_id = body.get("conversation_id") or body.get("conversationId") or ""
        call_sid = body.get("callSid") or body.get("call_sid")
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "event=outbound_call_failed voice_call_id=%s status=%d body=%s",
            voice_call_id,
            exc.response.status_code,
            exc.response.text[:500],
        )
        # Mark the row as failed.
        vc.call_status = "failed"
        vc.outcome = "failed"
        await db.commit()
        raise
    except httpx.HTTPError as exc:
        logger.warning(
            "event=outbound_call_transport_error voice_call_id=%s err=%s",
            voice_call_id,
            type(exc).__name__,
        )
        vc.call_status = "failed"
        vc.outcome = "failed"
        await db.commit()
        raise

    # 4. Update the row with ElevenLabs' conversation_id + Twilio sid.
    if conversation_id:
        vc.conversation_id = conversation_id
    if call_sid:
        vc.twilio_call_sid = call_sid
    await db.commit()

    logger.info(
        "event=outbound_call_placed voice_call_id=%s conversation_id=%s agent=%s to=%s",
        voice_call_id,
        conversation_id,
        agent_kind,
        to_number,
    )
    return voice_call_id, call_sid, conversation_id


def _purpose_for(agent_kind: AgentKind) -> str:
    return {
        "driver_agent": "driver_proactive_checkin",
        "detention_agent": "detention_escalation",
        "broker_update_agent": "broker_check_call",
    }.get(agent_kind, "other")


__all__ = ["place_outbound_call"]
