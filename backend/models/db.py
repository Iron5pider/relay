"""SQLAlchemy 2.x Declarative models — the canonical Postgres schema.

Mirrors `backend/models/schemas.py` field-for-field where the ORM can;
flattens nested Pydantic shapes (e.g. `Load.pickup` → `pickup_*` columns)
for Postgres-native querying. Primary keys are `TEXT` (not Postgres `UUID`)
because seed IDs like `br1a2b3c-0000-0000-0000-000000000010` contain
non-hex characters — see the `project_hero_demo_ids` memory + the plan at
`/Users/girikmanchanda/.claude/plans/polished-finding-stallman.md` for
the rationale. Enums are stored as plain `TEXT`; Pydantic layer validates.

Canonical indexes (per `backend/CLAUDE.md` §8):
- `loads(status, updated_at DESC)` — dashboard list.
- `voice_calls(load_id, started_at DESC)` — per-load call history.
- `webhook_events(provider, provider_event_id) UNIQUE` — idempotency.
Two additional convenience indexes: `loads(driver_id)`,
`exception_events(load_id, detected_at DESC)`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base. Do not instantiate."""


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_language: Mapped[str] = mapped_column(Text, nullable=False)
    truck_number: Mapped[str] = mapped_column(Text, nullable=False)
    current_lat: Mapped[float | None] = mapped_column(Float)
    current_lng: Mapped[float | None] = mapped_column(Float)
    hos_drive_remaining_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    hos_shift_remaining_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    hos_cycle_remaining_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    hos_remaining_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    fatigue_level: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="unknown"
    )
    last_checkin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_scheduled_checkin_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    # Load-balancer tiebreaker for consignment-assignment (2026-04-19).
    # Freshness component of the scoring formula prefers drivers who haven't
    # been handed work recently.
    last_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Broker(Base):
    __tablename__ = "brokers"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_update_channel: Mapped[str] = mapped_column(Text, nullable=False)


class Load(Base):
    __tablename__ = "loads"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    load_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Nullable as of 2026-04-19 — loads can land unassigned until the
    # dispatcher runs the consignment scorer and picks a driver.
    driver_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("drivers.id", ondelete="RESTRICT")
    )
    broker_id: Mapped[str] = mapped_column(
        Text, ForeignKey("brokers.id", ondelete="RESTRICT"), nullable=False
    )
    pickup_name: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_lat: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_lng: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_phone: Mapped[str | None] = mapped_column(Text)
    pickup_appointment: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    delivery_name: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_lat: Mapped[float] = mapped_column(Float, nullable=False)
    delivery_lng: Mapped[float] = mapped_column(Float, nullable=False)
    delivery_phone: Mapped[str | None] = mapped_column(Text)
    delivery_appointment: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    rate_linehaul: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    detention_rate_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    detention_free_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    arrived_at_stop_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detention_minutes_elapsed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    exception_flags: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    # Proof-of-delivery (2026-04-19). Written via POST /dispatcher/load/{id}/pod.
    pod_url: Mapped[str | None] = mapped_column(Text)
    pod_signed_by: Mapped[str | None] = mapped_column(Text)
    pod_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_loads_status_updated_at", "status", "updated_at"),
        Index("ix_loads_driver_id", "driver_id"),
    )


class VoiceCall(Base):
    __tablename__ = "voice_calls"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    load_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("loads.id", ondelete="SET NULL")
    )
    # Tools-contract additions (2026-04-19).
    # ElevenLabs conversation_id — unique lookup key for post_call webhook idempotency.
    conversation_id: Mapped[str | None] = mapped_column(Text, unique=True)
    agent_id: Mapped[str | None] = mapped_column(Text)
    driver_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("drivers.id", ondelete="SET NULL")
    )
    trigger_reason: Mapped[str | None] = mapped_column(Text)
    # dialing | in_progress | done | failed | no_answer | voicemail
    call_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="dialing"
    )
    analysis_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    from_number: Mapped[str] = mapped_column(Text, nullable=False)
    to_number: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="in_progress"
    )
    audio_url: Mapped[str | None] = mapped_column(Text)
    twilio_call_sid: Mapped[str] = mapped_column(Text, nullable=False)
    transcript: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    structured_data_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    # Anomaly-agent rationale when the call was fired from the Claude layer.
    # Null on hard-rule-fired calls. Surfaced verbatim in the AnomalyBadge tooltip.
    trigger_reasoning: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_voice_calls_load_started", "load_id", "started_at"),
        Index("ix_voice_calls_driver_id", "driver_id"),
    )


class TranscriptTurn(Base):
    __tablename__ = "transcript_turns"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    call_id: Mapped[str] = mapped_column(
        Text, ForeignKey("voice_calls.id", ondelete="CASCADE"), nullable=False
    )
    speaker: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class DetentionInvoice(Base):
    __tablename__ = "detention_invoices"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    load_id: Mapped[str] = mapped_column(
        Text, ForeignKey("loads.id", ondelete="RESTRICT"), nullable=False
    )
    call_id: Mapped[str] = mapped_column(
        Text, ForeignKey("voice_calls.id", ondelete="RESTRICT"), nullable=False
    )
    detention_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    pdf_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="draft"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ExceptionEvent(Base):
    __tablename__ = "exception_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    load_id: Mapped[str] = mapped_column(
        Text, ForeignKey("loads.id", ondelete="CASCADE"), nullable=False
    )
    driver_id: Mapped[str] = mapped_column(
        Text, ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    triggered_call_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("voice_calls.id", ondelete="SET NULL")
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index("ix_exception_events_load_detected", "load_id", "detected_at"),
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_event_id: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_webhook_events_provider_event",
        ),
    )


# --- Tools-contract tables (2026-04-19) -------------------------------------


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    driver_id: Mapped[str] = mapped_column(
        Text, ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False
    )
    call_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("voice_calls.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DetentionEvent(Base):
    __tablename__ = "detention_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    call_id: Mapped[str] = mapped_column(
        Text, ForeignKey("voice_calls.id", ondelete="CASCADE"), nullable=False
    )
    load_id: Mapped[str] = mapped_column(
        Text, ForeignKey("loads.id", ondelete="RESTRICT"), nullable=False
    )
    ap_contact_name: Mapped[str | None] = mapped_column(Text)
    ap_contact_method: Mapped[str | None] = mapped_column(Text)
    ap_contact_detail: Mapped[str | None] = mapped_column(Text)
    supervisor_name: Mapped[str | None] = mapped_column(Text)
    committed_to_pay: Mapped[bool] = mapped_column(nullable=False)
    detention_hours_confirmed: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    escalation_step_reached: Mapped[int | None] = mapped_column(Integer)
    contact_attempted: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Invoice(Base):
    """Tools-contract invoices table. Distinct from legacy `detention_invoices`.

    Written by `/internal/invoice/generate_detention`. PDF generation is stubbed
    for now (`pdf_url='pending'`); Block 3 adds real @react-pdf/renderer output.
    """

    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    load_id: Mapped[str] = mapped_column(
        Text, ForeignKey("loads.id", ondelete="RESTRICT"), nullable=False
    )
    call_id: Mapped[str] = mapped_column(
        Text, ForeignKey("voice_calls.id", ondelete="RESTRICT"), nullable=False
    )
    pdf_url: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="ready_for_review"
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Send audit (2026-04-19). Populated by POST /dispatcher/invoices/{id}/send.
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_to_email: Mapped[str | None] = mapped_column(Text)


class DispatcherNotification(Base):
    __tablename__ = "dispatcher_notifications"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    urgency: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    driver_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("drivers.id", ondelete="SET NULL")
    )
    load_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("loads.id", ondelete="SET NULL")
    )
    call_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("voice_calls.id", ondelete="SET NULL")
    )
    ack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DispatcherTask(Base):
    __tablename__ = "dispatcher_tasks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    priority: Mapped[str] = mapped_column(Text, nullable=False, server_default="med")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    related_call_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("voice_calls.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TranscriptSnapshot(Base):
    __tablename__ = "transcript_snapshots"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    call_id: Mapped[str] = mapped_column(
        Text, ForeignKey("voice_calls.id", ondelete="CASCADE"), nullable=False
    )
    key_quote: Mapped[str] = mapped_column(Text, nullable=False)
    quote_type: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp_in_call: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = [
    "Base",
    "Broker",
    "DetentionEvent",
    "DetentionInvoice",
    "DispatcherNotification",
    "DispatcherTask",
    "Driver",
    "ExceptionEvent",
    "Incident",
    "Invoice",
    "Load",
    "TranscriptSnapshot",
    "TranscriptTurn",
    "VoiceCall",
    "WebhookEvent",
]
