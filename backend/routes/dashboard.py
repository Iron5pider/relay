"""Dashboard / frontend-facing read endpoints + POD/invoice-send mutations.

All endpoints are Bearer-protected and envelope-wrapped. Four surfaces,
all under the `/dispatcher` prefix:

  1. Fleet live feed        — /dispatcher/fleet/live
                              /dispatcher/driver/{id}
                              /dispatcher/driver/{id}/timeline
  2. Detention live view    — /dispatcher/detentions/active
                              /dispatcher/detention/{load_id}
  3. Billing                — /dispatcher/invoices
                              /dispatcher/invoices/{id}
                              POST /dispatcher/invoices/{id}/send
  4. POD                    — POST /dispatcher/load/{id}/pod

The adapter picks between NavPro-live and seeded fleet data via
`settings.relay_adapter`. When `RELAY_ADAPTER=mock` the DB snapshot IS
the source; when `navpro`, we fall back to the DB for fields NavPro
doesn't expose (HOS, fatigue, detention state, broker context) per the
positioning memory.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.deps import get_db
from backend.models.db import (
    Broker,
    DetentionEvent,
    Driver,
    Invoice,
    Load,
    VoiceCall,
)
from backend.services.auth import require_relay_token
from backend.services.envelope import EnvelopeError, ok

logger = logging.getLogger("relay.routes.dashboard")

router = APIRouter(
    prefix="/dispatcher", dependencies=[Depends(require_relay_token)]
)


# ============================================================================
# Helpers
# ============================================================================


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _dec(v: Decimal | None) -> float | None:
    return None if v is None else float(v)


async def _broker_map(db: AsyncSession, ids: set[str]) -> dict[str, Broker]:
    if not ids:
        return {}
    q = await db.execute(select(Broker).where(Broker.id.in_(ids)))
    return {b.id: b for b in q.scalars().all()}


async def _driver_map(db: AsyncSession, ids: set[str]) -> dict[str, Driver]:
    if not ids:
        return {}
    q = await db.execute(select(Driver).where(Driver.id.in_(ids)))
    return {d.id: d for d in q.scalars().all()}


def _driver_lite(d: Driver | None) -> dict[str, Any] | None:
    if d is None:
        return None
    return {"id": d.id, "name": d.name, "truck_number": d.truck_number}


def _broker_lite(b: Broker | None) -> dict[str, Any] | None:
    if b is None:
        return None
    return {"id": b.id, "name": b.name}


def _driver_snapshot(d: Driver) -> dict[str, Any]:
    return {
        "driver_id": d.id,
        "name": d.name,
        "truck_number": d.truck_number,
        "phone": d.phone,
        "preferred_language": d.preferred_language,
        "current_lat": d.current_lat,
        "current_lng": d.current_lng,
        "status": d.status,
        "fatigue_level": d.fatigue_level,
        "hos_drive_remaining_minutes": d.hos_drive_remaining_minutes,
        "hos_shift_remaining_minutes": d.hos_shift_remaining_minutes,
        "hos_cycle_remaining_minutes": d.hos_cycle_remaining_minutes,
        "last_checkin_at": _iso(d.last_checkin_at),
        "next_scheduled_checkin_at": _iso(d.next_scheduled_checkin_at),
        "last_assigned_at": _iso(d.last_assigned_at),
        "updated_at": _iso(d.updated_at),
    }


def _load_snapshot(load: Load, broker: Broker | None = None) -> dict[str, Any]:
    return {
        "load_id": load.id,
        "load_number": load.load_number,
        "status": load.status,
        "pickup": {
            "name": load.pickup_name,
            "lat": load.pickup_lat,
            "lng": load.pickup_lng,
            "appointment": _iso(load.pickup_appointment),
        },
        "delivery": {
            "name": load.delivery_name,
            "lat": load.delivery_lat,
            "lng": load.delivery_lng,
            "appointment": _iso(load.delivery_appointment),
        },
        "rate_linehaul": _dec(load.rate_linehaul),
        "detention_rate_per_hour": _dec(load.detention_rate_per_hour),
        "detention_free_minutes": load.detention_free_minutes,
        "detention_minutes_elapsed": load.detention_minutes_elapsed,
        "arrived_at_stop_at": _iso(load.arrived_at_stop_at),
        "exception_flags": load.exception_flags or [],
        "broker": _broker_lite(broker),
        "pod": {
            "url": load.pod_url,
            "signed_by": load.pod_signed_by,
            "received_at": _iso(load.pod_received_at),
        },
    }


def _call_summary(c: VoiceCall) -> dict[str, Any]:
    return {
        "call_id": c.id,
        "conversation_id": c.conversation_id,
        "agent_id": c.agent_id,
        "direction": c.direction,
        "purpose": c.purpose,
        "call_status": c.call_status,
        "outcome": c.outcome,
        "trigger_reason": c.trigger_reason,
        "language": c.language,
        "duration_seconds": c.duration_seconds,
        "started_at": _iso(c.started_at),
        "ended_at": _iso(c.ended_at),
        "load_id": c.load_id,
        "driver_id": c.driver_id,
    }


# ============================================================================
# 1. Fleet live feed
# ============================================================================


@router.get("/fleet/live")
async def fleet_live(db: AsyncSession = Depends(get_db)):
    """All drivers with position + HOS + active load summary.

    Adapter mode surfaced so the dashboard can label the pin ("live" vs
    "simulated"). HOS + fatigue + active-load always come from the DB per
    the positioning memory — NavPro doesn't expose those.
    """
    dq = await db.execute(select(Driver).order_by(Driver.name))
    drivers = list(dq.scalars().all())

    # Pull every non-planned load per driver. Active statuses win when a
    # driver has multiple; otherwise fall back to the most recent delivered
    # load so the Delivered tab has something to render.
    lq = await db.execute(
        select(Load)
        .where(
            Load.driver_id.is_not(None),
            Load.status.in_(
                ["in_transit", "at_pickup", "at_delivery", "exception", "delivered"]
            ),
        )
        .order_by(Load.updated_at.desc())
    )
    all_loads = list(lq.scalars().all())
    _active_rank = {
        "exception": 0,
        "at_delivery": 1,
        "at_pickup": 2,
        "in_transit": 3,
        "delivered": 4,
    }
    by_driver: dict[str, Load] = {}
    for load in all_loads:
        if not load.driver_id:
            continue
        current = by_driver.get(load.driver_id)
        if current is None:
            by_driver[load.driver_id] = load
            continue
        if _active_rank[load.status] < _active_rank[current.status]:
            by_driver[load.driver_id] = load

    broker_ids = {load.broker_id for load in by_driver.values() if load.broker_id}
    brokers = await _broker_map(db, broker_ids)

    rows: list[dict[str, Any]] = []
    for d in drivers:
        snap = _driver_snapshot(d)
        active = by_driver.get(d.id)
        if active:
            snap["active_load"] = _load_snapshot(active, brokers.get(active.broker_id))
        else:
            snap["active_load"] = None
        rows.append(snap)

    return ok(
        {
            "adapter": settings.relay_adapter,
            "fetched_at": _iso(datetime.now(timezone.utc)),
            "count": len(rows),
            "drivers": rows,
        }
    )


@router.get("/driver/{driver_id}")
async def driver_detail(driver_id: str, db: AsyncSession = Depends(get_db)):
    d = await db.get(Driver, driver_id)
    if d is None:
        raise EnvelopeError(
            "driver_not_found", "No driver found for that ID.", http_status=404
        )

    # Active load (most recent non-terminal load on this driver).
    lq = await db.execute(
        select(Load)
        .where(Load.driver_id == driver_id)
        .order_by(Load.created_at.desc())
    )
    loads = list(lq.scalars().all())
    active = next(
        (load for load in loads if load.status not in {"delivered", "planned"}), None
    )
    broker = None
    if active and active.broker_id:
        broker = await db.get(Broker, active.broker_id)

    cq = await db.execute(
        select(VoiceCall)
        .where(VoiceCall.driver_id == driver_id)
        .order_by(VoiceCall.started_at.desc())
        .limit(5)
    )
    recent_calls = [_call_summary(c) for c in cq.scalars().all()]

    return ok(
        {
            **_driver_snapshot(d),
            "active_load": _load_snapshot(active, broker) if active else None,
            "load_history_count": len(loads),
            "recent_calls": recent_calls,
        }
    )


@router.get("/driver/{driver_id}/timeline")
async def driver_timeline(
    driver_id: str, limit: int = 25, db: AsyncSession = Depends(get_db)
):
    """Chronological feed of check-in + status events for one driver.

    Pulls voice calls (all purposes) and their post-call analysis as events.
    Loads assigned to this driver appear as `load_assigned` events too.
    """
    d = await db.get(Driver, driver_id)
    if d is None:
        raise EnvelopeError(
            "driver_not_found", "No driver found for that ID.", http_status=404
        )

    cq = await db.execute(
        select(VoiceCall)
        .where(VoiceCall.driver_id == driver_id)
        .order_by(VoiceCall.started_at.desc())
        .limit(limit)
    )
    calls = list(cq.scalars().all())

    lq = await db.execute(
        select(Load)
        .where(Load.driver_id == driver_id)
        .order_by(Load.created_at.desc())
        .limit(limit)
    )
    loads = list(lq.scalars().all())

    events: list[dict[str, Any]] = []
    for c in calls:
        summary = (c.analysis_json or {}).get("transcript_summary") or None
        events.append(
            {
                "kind": (
                    "driver_checkin"
                    if c.purpose in {"driver_checkin", "driver_proactive_checkin"}
                    else "voice_call"
                ),
                "timestamp": _iso(c.started_at),
                "label": f"{c.purpose} — {c.outcome}",
                "summary": summary,
                "call_id": c.id,
                "call_status": c.call_status,
                "purpose": c.purpose,
                "trigger_reason": c.trigger_reason,
            }
        )
    for load in loads:
        events.append(
            {
                "kind": "load_assigned",
                "timestamp": _iso(load.created_at),
                "label": f"assigned {load.load_number} ({load.pickup_name} → {load.delivery_name})",
                "summary": None,
                "load_id": load.id,
                "load_status": load.status,
            }
        )

    events.sort(key=lambda e: e["timestamp"] or "", reverse=True)
    return ok(
        {
            "driver_id": driver_id,
            "driver_name": d.name,
            "count": len(events[:limit]),
            "events": events[:limit],
        }
    )


# ============================================================================
# 2. Detention live view
# ============================================================================


def _detention_clock(load: Load, now: datetime) -> dict[str, Any]:
    """Compute the minutes-past-free + billable state for a load."""
    free = load.detention_free_minutes or 0
    elapsed = load.detention_minutes_elapsed or 0
    # If the load is currently at_stop, compute elapsed from arrival too.
    if load.arrived_at_stop_at is not None:
        stop_arrived = load.arrived_at_stop_at
        if stop_arrived.tzinfo is None:
            stop_arrived = stop_arrived.replace(tzinfo=timezone.utc)
        live_elapsed = int((now - stop_arrived).total_seconds() / 60)
        elapsed = max(elapsed, live_elapsed)
    past_free = max(elapsed - free, 0)
    billable_hours = past_free / 60.0
    billable_amount = (
        Decimal(billable_hours).quantize(Decimal("0.01"))
        * (load.detention_rate_per_hour or Decimal("0"))
    ).quantize(Decimal("0.01"))
    return {
        "elapsed_minutes": elapsed,
        "free_minutes": free,
        "minutes_past_free": past_free,
        "is_billable": past_free > 0,
        "projected_amount": float(billable_amount),
        "rate_per_hour": _dec(load.detention_rate_per_hour),
    }


@router.get("/detentions/active")
async def detentions_active(db: AsyncSession = Depends(get_db)):
    """List every load currently accruing detention — demo centerpiece.

    A load counts as "in detention" if either:
      - status == 'exception' AND detention_threshold_breached flag, OR
      - detention_minutes_elapsed > detention_free_minutes.
    """
    q = await db.execute(
        select(Load).where(
            (Load.status == "exception")
            | (Load.detention_minutes_elapsed > Load.detention_free_minutes)
        )
    )
    loads = list(q.scalars().all())

    broker_ids = {load.broker_id for load in loads}
    driver_ids = {load.driver_id for load in loads if load.driver_id}
    brokers = await _broker_map(db, broker_ids)
    drivers = await _driver_map(db, driver_ids)

    # Latest detention_escalation call per load.
    latest_calls: dict[str, VoiceCall] = {}
    if loads:
        load_ids = [load.id for load in loads]
        cq = await db.execute(
            select(VoiceCall)
            .where(
                VoiceCall.load_id.in_(load_ids),
                VoiceCall.purpose == "detention_escalation",
            )
            .order_by(VoiceCall.started_at.desc())
        )
        for c in cq.scalars().all():
            latest_calls.setdefault(c.load_id, c)

    # Invoices per load.
    invoices_by_load: dict[str, Invoice] = {}
    if loads:
        iq = await db.execute(
            select(Invoice).where(Invoice.load_id.in_([load.id for load in loads]))
        )
        for inv in iq.scalars().all():
            invoices_by_load.setdefault(inv.load_id, inv)

    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for load in loads:
        clock = _detention_clock(load, now)
        call = latest_calls.get(load.id)
        inv = invoices_by_load.get(load.id)
        rows.append(
            {
                "load_id": load.id,
                "load_number": load.load_number,
                "broker": _broker_lite(brokers.get(load.broker_id)),
                "driver": _driver_lite(drivers.get(load.driver_id)) if load.driver_id else None,
                "delivery_name": load.delivery_name,
                "status": load.status,
                "clock": clock,
                "latest_call": _call_summary(call) if call else None,
                "call_fired": call is not None,
                "invoice_id": inv.id if inv else None,
                "invoice_status": inv.status if inv else None,
                "invoice_amount": _dec(inv.amount) if inv else None,
            }
        )

    rows.sort(key=lambda r: r["clock"]["minutes_past_free"], reverse=True)
    return ok(
        {
            "count": len(rows),
            "fetched_at": _iso(now),
            "detentions": rows,
        }
    )


@router.get("/detention/{load_id}")
async def detention_detail(load_id: str, db: AsyncSession = Depends(get_db)):
    load = await db.get(Load, load_id)
    if load is None:
        raise EnvelopeError(
            "load_not_found", "No load found for that ID.", http_status=404
        )
    broker = await db.get(Broker, load.broker_id) if load.broker_id else None
    driver = await db.get(Driver, load.driver_id) if load.driver_id else None

    cq = await db.execute(
        select(VoiceCall)
        .where(
            VoiceCall.load_id == load_id,
            VoiceCall.purpose == "detention_escalation",
        )
        .order_by(VoiceCall.started_at.asc())
    )
    calls = list(cq.scalars().all())

    eq = await db.execute(
        select(DetentionEvent)
        .where(DetentionEvent.load_id == load_id)
        .order_by(DetentionEvent.created_at.asc())
    )
    events = list(eq.scalars().all())

    iq = await db.execute(select(Invoice).where(Invoice.load_id == load_id))
    invoice = iq.scalars().first()

    now = datetime.now(timezone.utc)
    return ok(
        {
            "load": _load_snapshot(load, broker),
            "driver": _driver_lite(driver),
            "clock": _detention_clock(load, now),
            "calls": [_call_summary(c) for c in calls],
            "events": [
                {
                    "event_id": e.id,
                    "call_id": e.call_id,
                    "ap_contact_name": e.ap_contact_name,
                    "ap_contact_method": e.ap_contact_method,
                    "ap_contact_detail": e.ap_contact_detail,
                    "committed_to_pay": e.committed_to_pay,
                    "detention_hours_confirmed": _dec(e.detention_hours_confirmed),
                    "notes": e.notes,
                    "escalation_step_reached": e.escalation_step_reached,
                    "contact_attempted": e.contact_attempted,
                    "created_at": _iso(e.created_at),
                }
                for e in events
            ],
            "invoice": (
                {
                    "invoice_id": invoice.id,
                    "amount": _dec(invoice.amount),
                    "status": invoice.status,
                    "pdf_url": invoice.pdf_url,
                    "sent_at": _iso(invoice.sent_at),
                    "sent_to_email": invoice.sent_to_email,
                    "generated_at": _iso(invoice.generated_at),
                }
                if invoice
                else None
            ),
        }
    )


# ============================================================================
# 3. Billing
# ============================================================================


@router.get("/invoices")
async def list_invoices(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Invoice).order_by(Invoice.generated_at.desc())
    if status:
        q = q.where(Invoice.status == status)
    iq = await db.execute(q)
    invoices = list(iq.scalars().all())

    load_ids = {inv.load_id for inv in invoices}
    lq = await db.execute(select(Load).where(Load.id.in_(load_ids))) if load_ids else None
    loads = {load.id: load for load in (lq.scalars().all() if lq else [])}

    broker_ids = {load.broker_id for load in loads.values()}
    brokers = await _broker_map(db, broker_ids)

    # Aggregate totals by status (useful summary strip at the top of the page).
    tot_q = await db.execute(
        select(Invoice.status, func.sum(Invoice.amount), func.count())
        .group_by(Invoice.status)
    )
    totals = [
        {"status": row[0], "amount": _dec(row[1]), "count": row[2]}
        for row in tot_q.all()
    ]

    rows: list[dict[str, Any]] = []
    for inv in invoices:
        load = loads.get(inv.load_id)
        rows.append(
            {
                "invoice_id": inv.id,
                "amount": _dec(inv.amount),
                "status": inv.status,
                "pdf_url": inv.pdf_url,
                "generated_at": _iso(inv.generated_at),
                "sent_at": _iso(inv.sent_at),
                "sent_to_email": inv.sent_to_email,
                "load_number": load.load_number if load else None,
                "load_id": inv.load_id,
                "broker": _broker_lite(brokers.get(load.broker_id)) if load else None,
                "pod_received": bool(load and load.pod_received_at),
            }
        )
    return ok({"count": len(rows), "totals": totals, "invoices": rows})


@router.get("/invoices/{invoice_id}")
async def invoice_detail(invoice_id: str, db: AsyncSession = Depends(get_db)):
    inv = await db.get(Invoice, invoice_id)
    if inv is None:
        raise EnvelopeError(
            "invoice_not_found", "No invoice found for that ID.", http_status=404
        )
    load = await db.get(Load, inv.load_id)
    broker = await db.get(Broker, load.broker_id) if load else None
    driver = await db.get(Driver, load.driver_id) if load and load.driver_id else None
    call = await db.get(VoiceCall, inv.call_id) if inv.call_id else None

    return ok(
        {
            "invoice_id": inv.id,
            "amount": _dec(inv.amount),
            "status": inv.status,
            "pdf_url": inv.pdf_url,
            "generated_at": _iso(inv.generated_at),
            "sent_at": _iso(inv.sent_at),
            "sent_to_email": inv.sent_to_email,
            "load": _load_snapshot(load, broker) if load else None,
            "driver": _driver_lite(driver),
            "triggering_call": _call_summary(call) if call else None,
        }
    )


class InvoiceSendRequest(BaseModel):
    # Plain str (not EmailStr) to avoid an extra dep on `email-validator`. A
    # lightweight shape check below catches obvious typos; actual delivery
    # validation lives in the email provider when we wire one up.
    to_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    cc_email: str | None = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/invoices/{invoice_id}/send")
async def send_invoice(
    invoice_id: str,
    body: InvoiceSendRequest,
    db: AsyncSession = Depends(get_db),
):
    """Mark an invoice as sent and stamp the destination email.

    We don't actually dispatch email here — that's an integration concern
    (SendGrid/Postmark). The state transition + audit trail is what the
    dashboard needs. The real-world "send" lands in a future phase.
    """
    inv = await db.get(Invoice, invoice_id)
    if inv is None:
        raise EnvelopeError(
            "invoice_not_found", "No invoice found for that ID.", http_status=404
        )
    if inv.status == "sent":
        raise EnvelopeError(
            "already_sent",
            f"Invoice {invoice_id} was already sent at {_iso(inv.sent_at)}.",
            http_status=409,
        )
    now = datetime.now(timezone.utc)
    inv.sent_at = now
    inv.sent_to_email = str(body.to_email)
    inv.status = "sent"
    await db.commit()

    logger.info(
        "event=invoice_sent invoice_id=%s to=%s amount=%s",
        inv.id,
        body.to_email,
        inv.amount,
    )
    return ok(
        {
            "invoice_id": inv.id,
            "status": inv.status,
            "sent_at": _iso(inv.sent_at),
            "sent_to_email": inv.sent_to_email,
            "cc_email": body.cc_email,
        }
    )


# ============================================================================
# 4. POD (Proof of Delivery)
# ============================================================================


class PodRecordRequest(BaseModel):
    pod_url: str = Field(min_length=5)
    signed_by: str = Field(min_length=1, max_length=200)


@router.post("/load/{load_id}/pod")
async def record_pod(
    load_id: str, body: PodRecordRequest, db: AsyncSession = Depends(get_db)
):
    """Record proof-of-delivery for a load.

    The frontend uploads the signed BOL image to its own storage (S3 /
    Supabase Storage) and hands us the URL. We record it + who signed
    and bump the load to `delivered` so the POD card on the billing
    screen lights up.
    """
    load = await db.get(Load, load_id)
    if load is None:
        raise EnvelopeError(
            "load_not_found", "No load found for that ID.", http_status=404
        )
    if load.pod_received_at is not None:
        raise EnvelopeError(
            "pod_already_recorded",
            f"POD for load {load.load_number} was already recorded at {_iso(load.pod_received_at)}.",
            http_status=409,
        )

    now = datetime.now(timezone.utc)
    load.pod_url = body.pod_url
    load.pod_signed_by = body.signed_by
    load.pod_received_at = now
    if load.status != "delivered":
        load.status = "delivered"
    await db.commit()

    logger.info(
        "event=pod_recorded load=%s signed_by=%s", load.load_number, body.signed_by
    )
    return ok(
        {
            "load_id": load.id,
            "load_number": load.load_number,
            "status": load.status,
            "pod_url": load.pod_url,
            "pod_signed_by": load.pod_signed_by,
            "pod_received_at": _iso(load.pod_received_at),
        }
    )


# ============================================================================
# 5. Calls section (list + full detail)
# ============================================================================


def _extract_evaluation_criteria(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize `evaluation_criteria_results` into a stable list.

    ElevenLabs emits this as a dict-of-dicts keyed by criteria_id. We flatten
    into a sorted list with `failure` first so the dispatcher sees what went
    wrong at the top of the tab.
    """
    raw = analysis.get("evaluation_criteria_results") or {}
    if isinstance(raw, list):
        rows = raw
    else:
        rows = [
            {"criteria_id": key, **(val or {})}
            for key, val in raw.items()
            if isinstance(val, dict)
        ]
    rank = {"failure": 0, "unknown": 1, "success": 2}
    rows.sort(key=lambda r: rank.get(str(r.get("result") or ""), 3))
    return [
        {
            "criteria_id": r.get("criteria_id"),
            "result": r.get("result"),
            "rationale": r.get("rationale"),
        }
        for r in rows
    ]


def _extract_data_collection(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize `data_collection_results` into a list of fields."""
    raw = analysis.get("data_collection_results") or {}
    out: list[dict[str, Any]] = []
    if isinstance(raw, list):
        items = raw
    else:
        items = [
            {"data_collection_id": key, **(val or {})}
            for key, val in raw.items()
            if isinstance(val, dict)
        ]
    # Surface the useful driver-flow fields first.
    priority = {
        "issues_flagged": 0,
        "issue_type": 1,
        "issue_description": 2,
        "ready_status": 3,
        "hos_remaining_min": 4,
        "fuel_level_pct": 5,
        "location_city": 6,
        "new_eta_iso": 7,
        "safety_status": 8,
        "parking_accepted_suggestion": 9,
        "parking_plan": 10,
        "escalation_requested": 11,
        "call_language": 12,
        "repair_shop_selected": 13,
    }
    items.sort(key=lambda it: priority.get(str(it.get("data_collection_id")), 99))
    for it in items:
        schema = it.get("json_schema") or {}
        out.append(
            {
                "data_collection_id": it.get("data_collection_id"),
                "value": it.get("value"),
                "rationale": it.get("rationale"),
                "description": schema.get("description"),
                "type": schema.get("type"),
            }
        )
    return out


def _transcript_turns(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    turns: list[dict[str, Any]] = []
    for t in raw:
        if not isinstance(t, dict):
            continue
        turns.append(
            {
                "role": t.get("role"),
                "message": t.get("message"),
                "time_in_call_secs": t.get("time_in_call_secs"),
                "tool_calls": t.get("tool_calls") or [],
                "interrupted": t.get("interrupted"),
            }
        )
    return turns


def _call_list_row(call: VoiceCall, analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        **_call_summary(call),
        "termination_reason": call.termination_reason,
        "call_summary_title": analysis.get("call_summary_title"),
        "transcript_summary": analysis.get("transcript_summary"),
        "has_audio": analysis.get("has_audio"),
        "cost": analysis.get("cost"),
    }


@router.get("/calls")
async def list_calls(
    agent_id: str | None = None,
    purpose: str | None = None,
    outcome: str | None = None,
    call_status: str | None = None,
    driver_id: str | None = None,
    load_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    q = select(VoiceCall).order_by(VoiceCall.started_at.desc()).limit(max(1, min(limit, 200)))
    if agent_id:
        q = q.where(VoiceCall.agent_id == agent_id)
    if purpose:
        q = q.where(VoiceCall.purpose == purpose)
    if outcome:
        q = q.where(VoiceCall.outcome == outcome)
    if call_status:
        q = q.where(VoiceCall.call_status == call_status)
    if driver_id:
        q = q.where(VoiceCall.driver_id == driver_id)
    if load_id:
        q = q.where(VoiceCall.load_id == load_id)

    result = await db.execute(q)
    calls = list(result.scalars().all())
    rows = [_call_list_row(c, c.analysis_json or {}) for c in calls]
    return ok({"count": len(rows), "calls": rows})


@router.get("/calls/{call_id}")
async def call_detail(call_id: str, db: AsyncSession = Depends(get_db)):
    """Accepts either voice_calls.id or voice_calls.conversation_id."""
    call = await db.get(VoiceCall, call_id)
    if call is None:
        cq = await db.execute(
            select(VoiceCall).where(VoiceCall.conversation_id == call_id)
        )
        call = cq.scalars().first()
    if call is None:
        raise EnvelopeError(
            "call_not_found", "No call found for that ID.", http_status=404
        )

    analysis = call.analysis_json or {}
    driver = await db.get(Driver, call.driver_id) if call.driver_id else None
    load = await db.get(Load, call.load_id) if call.load_id else None
    broker = await db.get(Broker, load.broker_id) if (load and load.broker_id) else None
    phone_call = analysis.get("phone_call") or {}

    return ok(
        {
            **_call_summary(call),
            "termination_reason": call.termination_reason,
            "trigger_reasoning": call.trigger_reasoning,
            "audio_url": call.audio_url,
            "call_summary_title": analysis.get("call_summary_title"),
            "transcript_summary": analysis.get("transcript_summary"),
            "call_successful": analysis.get("call_successful"),
            "has_audio": analysis.get("has_audio"),
            "cost": analysis.get("cost"),
            "phone_call": {
                "type": phone_call.get("type"),
                "direction": phone_call.get("direction") or call.direction,
                "from_number": phone_call.get("from_number") or call.from_number,
                "to_number": phone_call.get("to_number") or call.to_number,
                "phone_number_id": phone_call.get("phone_number_id"),
                "call_sid": phone_call.get("call_sid") or call.twilio_call_sid,
                "agent_number": phone_call.get("agent_number"),
                "external_number": phone_call.get("external_number"),
            },
            "transcript": _transcript_turns(call.transcript),
            "evaluation_criteria_results": _extract_evaluation_criteria(analysis),
            "data_collection_results": _extract_data_collection(analysis),
            "driver": _driver_lite(driver),
            "load": _load_snapshot(load, broker) if load else None,
            "broker": _broker_lite(broker),
        }
    )


__all__ = ["router"]
