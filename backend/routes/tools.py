"""ElevenLabs agent tool handlers.

Every route:
- Bearer-auth via `require_relay_token` (401 if missing/wrong).
- Response wrapped in `{ok, data, error}` envelope.
- Structured log line: `event=tool_call tool=<name> call_id=<conv_id> latency_ms=<n>`.
- Raises `EnvelopeError` for foreseeable failures (unknown load_id, etc.) so
  the handler catches + returns a speakable message rather than 500.

See `API_DOCS/tools_contract.md` §2–§4 for wire-level shapes. Shapes here
mirror the spec verbatim; the `data` field is what goes into the envelope.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_db
from backend.models.db import (
    Broker,
    DetentionEvent,
    DispatcherNotification,
    DispatcherTask,
    Driver,
    Incident,
    Load,
    TranscriptSnapshot,
)
from backend.models.tool_schemas import (
    ConfirmDetentionRequest,
    LogIssueRequest,
    MarkBrokerUpdatedRequest,
    MarkRefusedRequest,
    NotifyDispatcherRequest,
    RequestDispatcherCallbackRequest,
    TranscriptSnapshotRequest,
    UpdateEtaRequest,
    UpdateHosRequest,
    UpdateStatusRequest,
)
from backend.services.auth import require_relay_token
from backend.services.envelope import EnvelopeError, ok
from backend.services.parking import nearby_parking
from backend.services.repair import nearby_repair_shops

logger = logging.getLogger("relay.tools")

router = APIRouter(dependencies=[Depends(require_relay_token)])


def _log(tool: str, call_id: str | None, start: float) -> None:
    logger.info(
        "event=tool_call tool=%s call_id=%s latency_ms=%d",
        tool,
        call_id or "",
        int((time.monotonic() - start) * 1000),
    )


# =============================================================================
# driver_agent tools (§2)
# =============================================================================


@router.get("/tools/driver/context")
async def get_driver_context(
    driver_id: str = Query(...), db: AsyncSession = Depends(get_db)
):
    start = time.monotonic()
    driver = await db.get(Driver, driver_id)
    if driver is None:
        raise EnvelopeError(
            "driver_not_found",
            "No driver found for that ID. Please check with the dispatcher.",
            http_status=404,
        )

    # Active load (most recent) if any.
    load_q = await db.execute(
        select(Load).where(Load.driver_id == driver_id).order_by(Load.created_at.desc())
    )
    active_load = load_q.scalars().first()

    first_name = driver.name.split(" ", 1)[0] if driver.name else ""
    city = None
    if driver.current_lat is not None and driver.current_lng is not None:
        city = None  # Block 2 adds reverse geocoding

    last_gps: dict[str, Any] | None = None
    if driver.current_lat is not None and driver.current_lng is not None:
        last_gps = {
            "lat": driver.current_lat,
            "lng": driver.current_lng,
            "city": city or "unknown",
            "updated_at": driver.updated_at.isoformat().replace("+00:00", "Z")
            if driver.updated_at
            else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    data = {
        "driver_id": driver.id,
        "name": driver.name,
        "first_name": first_name,
        "truck_number": driver.truck_number,
        "current_load_id": active_load.id if active_load else None,
        "last_gps": last_gps,
        "hos_drive_remaining_min": driver.hos_drive_remaining_minutes,
        "hos_shift_remaining_min": driver.hos_shift_remaining_minutes,
        "fuel_last_known_pct": None,  # not tracked in schema yet
        "preferred_language": driver.preferred_language,
        "fatigue_level": driver.fatigue_level,
    }
    _log("get_driver_context", None, start)
    return ok(data)


@router.post("/tools/driver/update_hos")
async def update_hos(body: UpdateHosRequest, db: AsyncSession = Depends(get_db)):
    start = time.monotonic()
    driver = await db.get(Driver, body.driver_id)
    if driver is None:
        raise EnvelopeError("driver_not_found", "No driver found for that ID.", http_status=404)
    driver.hos_drive_remaining_minutes = body.hos_remaining_min
    driver.hos_remaining_minutes = body.hos_remaining_min
    driver.status = body.status
    driver.updated_at = datetime.now(timezone.utc)
    await db.commit()
    _log("update_hos", body.call_id, start)
    return ok({"updated_at": driver.updated_at.isoformat().replace("+00:00", "Z")})


@router.post("/tools/driver/update_status")
async def update_status(body: UpdateStatusRequest, db: AsyncSession = Depends(get_db)):
    start = time.monotonic()
    driver = await db.get(Driver, body.driver_id)
    if driver is None:
        raise EnvelopeError("driver_not_found", "No driver found for that ID.", http_status=404)
    driver.status = body.status
    driver.updated_at = datetime.now(timezone.utc)
    await db.commit()
    _log("update_status", body.call_id, start)
    return ok({"updated_at": driver.updated_at.isoformat().replace("+00:00", "Z")})


@router.post("/tools/driver/log_issue")
async def log_issue(body: LogIssueRequest, db: AsyncSession = Depends(get_db)):
    start = time.monotonic()
    driver = await db.get(Driver, body.driver_id)
    if driver is None:
        raise EnvelopeError("driver_not_found", "No driver found for that ID.", http_status=404)

    incident_id = str(uuid.uuid4())
    call_uuid = await _resolve_call_id(db, body.call_id)
    inc = Incident(
        id=incident_id,
        driver_id=body.driver_id,
        call_id=call_uuid,
        type=body.type.value if hasattr(body.type, "value") else body.type,
        severity=body.severity,
        description=body.description,
    )
    db.add(inc)
    await db.commit()
    _log("log_issue", body.call_id, start)
    return ok({"incident_id": incident_id})


@router.post("/tools/trip/update_eta")
async def update_eta(body: UpdateEtaRequest, db: AsyncSession = Depends(get_db)):
    start = time.monotonic()
    # For the hackathon we treat `trip_id` as `load_id`.
    load = await db.get(Load, body.trip_id)
    if load is None:
        raise EnvelopeError(
            "load_not_found", "No load found for that trip ID.", http_status=404
        )
    previous_eta = load.delivery_appointment
    try:
        new_eta = datetime.fromisoformat(body.new_eta_iso.replace("Z", "+00:00"))
    except ValueError:
        raise EnvelopeError("invalid_eta", "new_eta_iso must be ISO 8601.", http_status=400)

    delta_minutes = int((new_eta - previous_eta).total_seconds() // 60)
    load.delivery_appointment = new_eta
    load.updated_at = datetime.now(timezone.utc)

    # Side effect: if drift > 30 min, drop a dispatcher_notifications row so
    # the FE can surface "Notify broker?" one-click action.
    if abs(delta_minutes) > 30:
        notif_id = str(uuid.uuid4())
        db.add(
            DispatcherNotification(
                id=notif_id,
                urgency="med",
                summary=(
                    f"ETA slip on load {load.load_number}: {delta_minutes:+d}min "
                    f"(reason: {body.reason[:100]}) — broker notify candidate"
                ),
                load_id=load.id,
                driver_id=load.driver_id,
                call_id=await _resolve_call_id(db, body.call_id),
            )
        )

    await db.commit()
    _log("update_eta", body.call_id, start)
    return ok(
        {
            "trip_id": load.id,
            "previous_eta": previous_eta.isoformat().replace("+00:00", "Z"),
            "new_eta": new_eta.isoformat().replace("+00:00", "Z"),
            "delta_minutes": delta_minutes,
        }
    )


@router.get("/tools/parking/nearby")
async def lookup_parking(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_mi: float = Query(50, ge=1, le=500),
):
    start = time.monotonic()
    spots = nearby_parking(lat, lng, radius_mi=radius_mi, limit=5)
    _log("lookup_parking", None, start)
    return ok(spots)


@router.get("/tools/repair/nearby")
async def find_repair_shop(
    lat: float = Query(...),
    lng: float = Query(...),
    service: str | None = Query(None),
):
    start = time.monotonic()
    shops = nearby_repair_shops(lat, lng, service=service, limit=3)
    _log("find_repair_shop", None, start)
    return ok(shops)


@router.post("/tools/dispatcher/notify")
async def notify_dispatcher(
    body: NotifyDispatcherRequest, db: AsyncSession = Depends(get_db)
):
    start = time.monotonic()
    notif_id = str(uuid.uuid4())
    db.add(
        DispatcherNotification(
            id=notif_id,
            urgency=body.urgency.value if hasattr(body.urgency, "value") else body.urgency,
            summary=body.summary,
            driver_id=body.driver_id,
            load_id=body.load_id,
            call_id=await _resolve_call_id(db, body.call_id) if body.call_id else None,
        )
    )
    await db.commit()
    _log("notify_dispatcher", body.call_id, start)
    return ok({"notification_id": notif_id})


# =============================================================================
# detention_agent tools (§3)
# =============================================================================


@router.get("/tools/load/rate_con_terms")
async def get_rate_con_terms(
    load_id: str = Query(...), db: AsyncSession = Depends(get_db)
):
    start = time.monotonic()
    load = await db.get(Load, load_id)
    if load is None:
        raise EnvelopeError("load_not_found", "No load found for that ID.", http_status=404)
    broker = await db.get(Broker, load.broker_id)

    data = {
        "load_id": load.id,
        "load_number": load.load_number,
        "detention_free_minutes": load.detention_free_minutes,
        "detention_rate_per_hour": float(load.detention_rate_per_hour),
        "tonu_rate": 150.00,  # not modeled per-load yet; contract default
        "layover_rate": 200.00,
        "receiver_name": load.delivery_name,
        "receiver_address": load.delivery_name,  # address not modeled; reuse name
        "appointment_dt": load.delivery_appointment.isoformat().replace("+00:00", "Z"),
        "broker_name": broker.name if broker else "",
        "rate_linehaul": float(load.rate_linehaul),
    }
    _log("get_rate_con_terms", None, start)
    return ok(data)


@router.post("/tools/detention/confirm")
async def confirm_detention(
    body: ConfirmDetentionRequest, db: AsyncSession = Depends(get_db)
):
    start = time.monotonic()
    load = await db.get(Load, body.load_id)
    if load is None:
        raise EnvelopeError("load_not_found", "No load found for that ID.", http_status=404)
    call_uuid = await _resolve_call_id(db, body.call_id)
    if call_uuid is None:
        raise EnvelopeError(
            "call_not_found",
            "This call isn't tracked. Please retry after hangup.",
            http_status=404,
        )
    event_id = str(uuid.uuid4())
    db.add(
        DetentionEvent(
            id=event_id,
            call_id=call_uuid,
            load_id=load.id,
            ap_contact_name=body.ap_contact_name,
            ap_contact_method=body.ap_contact_method,
            ap_contact_detail=body.ap_contact_detail,
            supervisor_name=body.supervisor_name,
            committed_to_pay=body.committed_to_pay,
            detention_hours_confirmed=body.detention_hours_confirmed,
            notes=body.notes,
        )
    )
    await db.commit()
    _log("confirm_detention", body.call_id, start)
    # Invoice generation is triggered post-call (§6.3) — don't block here.
    return ok(
        {"detention_event_id": event_id, "invoice_generation_queued": True}
    )


@router.post("/tools/detention/refused")
async def mark_refused(
    body: MarkRefusedRequest, db: AsyncSession = Depends(get_db)
):
    start = time.monotonic()
    load = await db.get(Load, body.load_id)
    if load is None:
        raise EnvelopeError("load_not_found", "No load found for that ID.", http_status=404)
    call_uuid = await _resolve_call_id(db, body.call_id)
    if call_uuid is None:
        raise EnvelopeError(
            "call_not_found",
            "This call isn't tracked. Please retry.",
            http_status=404,
        )
    event_id = str(uuid.uuid4())
    db.add(
        DetentionEvent(
            id=event_id,
            call_id=call_uuid,
            load_id=load.id,
            committed_to_pay=False,
            notes=body.reason,
            escalation_step_reached=body.escalation_step_reached,
            contact_attempted=body.contact_attempted,
        )
    )
    await db.commit()
    _log("mark_refused", body.call_id, start)
    return ok({"detention_event_id": event_id})


@router.post("/tools/call/transcript_snapshot")
async def transcript_snapshot(
    body: TranscriptSnapshotRequest, db: AsyncSession = Depends(get_db)
):
    start = time.monotonic()
    call_uuid = await _resolve_call_id(db, body.call_id)
    if call_uuid is None:
        raise EnvelopeError(
            "call_not_found",
            "This call isn't tracked.",
            http_status=404,
        )
    snap_id = str(uuid.uuid4())
    db.add(
        TranscriptSnapshot(
            id=snap_id,
            call_id=call_uuid,
            key_quote=body.key_quote,
            quote_type=body.quote_type,
        )
    )
    await db.commit()
    _log("transcript_snapshot", body.call_id, start)
    return ok({"snapshot_id": snap_id})


# =============================================================================
# broker_update_agent tools (§4)
# =============================================================================


@router.get("/tools/load/status_for_broker")
async def get_load_status_for_broker(
    load_id: str = Query(...), db: AsyncSession = Depends(get_db)
):
    start = time.monotonic()
    load = await db.get(Load, load_id)
    if load is None:
        raise EnvelopeError("load_not_found", "No load found for that ID.", http_status=404)
    driver = await db.get(Driver, load.driver_id)
    first_name = driver.name.split(" ", 1)[0] if driver and driver.name else ""

    now = datetime.now(timezone.utc)
    schedule_delta = int((now - load.delivery_appointment).total_seconds() // 60)
    on_schedule = schedule_delta <= 0

    data = {
        "load_id": load.id,
        "load_number": load.load_number,
        "driver_first_name": first_name,
        "last_gps_city": None,  # Block 2 reverse geocode
        "miles_remaining": None,  # not modeled
        "eta_iso": load.delivery_appointment.isoformat().replace("+00:00", "Z"),
        "eta_time_pst": None,
        "appointment_time_pst": None,
        "on_schedule": on_schedule,
        "schedule_delta_minutes": schedule_delta,
        "status": load.status,
    }
    _log("get_load_status_for_broker", None, start)
    return ok(data)


@router.post("/tools/broker/update_confirmed")
async def mark_broker_updated(
    body: MarkBrokerUpdatedRequest, db: AsyncSession = Depends(get_db)
):
    start = time.monotonic()
    load = await db.get(Load, body.load_id)
    if load is None:
        raise EnvelopeError("load_not_found", "No load found for that ID.", http_status=404)

    # Log as a dispatcher_notification with urgency=low so the UI has a trace.
    # A dedicated `broker_updates` table could come later; this is sufficient.
    update_id = str(uuid.uuid4())
    vm_tag = "[voicemail] " if body.voicemail else ""
    ack_tag = " (ack received)" if body.broker_ack_received else ""
    db.add(
        DispatcherNotification(
            id=update_id,
            urgency="low",
            summary=(
                f"{vm_tag}Broker update confirmed for {load.load_number} via "
                f"{body.broker_rep_name or 'broker rep'}{ack_tag}. "
                f"Notes: {(body.notes or '')[:150]}"
            ),
            load_id=load.id,
            driver_id=load.driver_id,
            call_id=await _resolve_call_id(db, body.call_id),
        )
    )
    await db.commit()
    _log("mark_broker_updated", body.call_id, start)
    return ok({"update_id": update_id})


@router.post("/tools/broker/escalation_request")
async def request_dispatcher_callback(
    body: RequestDispatcherCallbackRequest, db: AsyncSession = Depends(get_db)
):
    start = time.monotonic()
    task_id = str(uuid.uuid4())
    call_uuid = await _resolve_call_id(db, body.call_id)
    db.add(
        DispatcherTask(
            id=task_id,
            priority="high",
            title=f"Broker callback — {body.broker_rep_name or 'broker'} on load {body.load_id}",
            body=body.reason,
            related_call_id=call_uuid,
        )
    )
    await db.commit()
    _log("request_dispatcher_callback", body.call_id, start)
    return ok({"callback_request_id": task_id})


# =============================================================================
# helpers
# =============================================================================


async def _resolve_call_id(db: AsyncSession, raw: str | None) -> str | None:
    """Callers pass `{{system__conversation_id}}` from ElevenLabs, which is the
    conversation_id (not our voice_calls.id). Resolve → voice_calls.id.

    Accepts either: if it matches a conversation_id, returns that row's UUID.
    If it matches a voice_calls.id directly (our internal UUID), returns it.
    Returns None if nothing matches.
    """
    if not raw:
        return None
    from backend.models.db import VoiceCall

    # Try conversation_id match first.
    r = await db.execute(
        select(VoiceCall.id).where(VoiceCall.conversation_id == raw)
    )
    vid = r.scalar_one_or_none()
    if vid:
        return vid
    # Fall back: maybe they passed our own UUID.
    r = await db.execute(select(VoiceCall.id).where(VoiceCall.id == raw))
    return r.scalar_one_or_none()


__all__ = ["router"]
