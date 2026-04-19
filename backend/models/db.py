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
    driver_id: Mapped[str] = mapped_column(
        Text, ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False
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


__all__ = [
    "Base",
    "Broker",
    "DetentionInvoice",
    "Driver",
    "ExceptionEvent",
    "Load",
    "TranscriptTurn",
    "VoiceCall",
    "WebhookEvent",
]
