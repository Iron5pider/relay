"""Initial schema — 8 canonical tables + 5 indexes + idempotency unique.

Revision ID: 20260419_0000
Revises: None
Create Date: 2026-04-19

Per `backend/CLAUDE.md` §8: drivers, brokers, loads, voice_calls,
transcript_turns, detention_invoices, exception_events, webhook_events.

All PKs are TEXT (not UUID) — seed IDs like `br1a2b3c-…` contain non-hex
characters. Timestamps are TIMESTAMPTZ. Flexible fields (transcripts,
payloads, exception flags) are JSONB. Enums are TEXT + Pydantic-layer
validation to avoid Alembic ENUM-alter churn when we add values.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260419_0000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brokers",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("preferred_update_channel", sa.Text(), nullable=False),
    )

    op.create_table(
        "drivers",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("preferred_language", sa.Text(), nullable=False),
        sa.Column("truck_number", sa.Text(), nullable=False),
        sa.Column("current_lat", sa.Float()),
        sa.Column("current_lng", sa.Float()),
        sa.Column("hos_drive_remaining_minutes", sa.Integer(), nullable=False),
        sa.Column("hos_shift_remaining_minutes", sa.Integer(), nullable=False),
        sa.Column("hos_cycle_remaining_minutes", sa.Integer(), nullable=False),
        sa.Column("hos_remaining_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "fatigue_level",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("last_checkin_at", sa.DateTime(timezone=True)),
        sa.Column("next_scheduled_checkin_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "loads",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("load_number", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "driver_id",
            sa.Text(),
            sa.ForeignKey("drivers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "broker_id",
            sa.Text(),
            sa.ForeignKey("brokers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("pickup_name", sa.Text(), nullable=False),
        sa.Column("pickup_lat", sa.Float(), nullable=False),
        sa.Column("pickup_lng", sa.Float(), nullable=False),
        sa.Column("pickup_phone", sa.Text()),
        sa.Column("pickup_appointment", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivery_name", sa.Text(), nullable=False),
        sa.Column("delivery_lat", sa.Float(), nullable=False),
        sa.Column("delivery_lng", sa.Float(), nullable=False),
        sa.Column("delivery_phone", sa.Text()),
        sa.Column("delivery_appointment", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rate_linehaul", sa.Numeric(10, 2), nullable=False),
        sa.Column("detention_rate_per_hour", sa.Numeric(10, 2), nullable=False),
        sa.Column("detention_free_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("arrived_at_stop_at", sa.DateTime(timezone=True)),
        sa.Column(
            "detention_minutes_elapsed",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "exception_flags",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_loads_status_updated_at",
        "loads",
        ["status", sa.text("updated_at DESC")],
    )
    op.create_index("ix_loads_driver_id", "loads", ["driver_id"])

    op.create_table(
        "voice_calls",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "load_id",
            sa.Text(),
            sa.ForeignKey("loads.id", ondelete="SET NULL"),
        ),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("from_number", sa.Text(), nullable=False),
        sa.Column("to_number", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column(
            "outcome",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'in_progress'"),
        ),
        sa.Column("audio_url", sa.Text()),
        sa.Column("twilio_call_sid", sa.Text(), nullable=False),
        sa.Column(
            "transcript",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "structured_data_json",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("trigger_reasoning", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_voice_calls_load_started",
        "voice_calls",
        ["load_id", sa.text("started_at DESC")],
    )

    op.create_table(
        "transcript_turns",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "call_id",
            sa.Text(),
            sa.ForeignKey("voice_calls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("speaker", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
    )

    op.create_table(
        "detention_invoices",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "load_id",
            sa.Text(),
            sa.ForeignKey("loads.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "call_id",
            sa.Text(),
            sa.ForeignKey("voice_calls.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("detention_minutes", sa.Integer(), nullable=False),
        sa.Column("rate_per_hour", sa.Numeric(10, 2), nullable=False),
        sa.Column("amount_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("pdf_url", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "exception_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "load_id",
            sa.Text(),
            sa.ForeignKey("loads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "driver_id",
            sa.Text(),
            sa.ForeignKey("drivers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "triggered_call_id",
            sa.Text(),
            sa.ForeignKey("voice_calls.id", ondelete="SET NULL"),
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_exception_events_load_detected",
        "exception_events",
        ["load_id", sa.text("detected_at DESC")],
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_event_id", sa.Text(), nullable=False),
        sa.Column(
            "body",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_webhook_events_provider_event",
        ),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_index("ix_exception_events_load_detected", table_name="exception_events")
    op.drop_table("exception_events")
    op.drop_table("detention_invoices")
    op.drop_table("transcript_turns")
    op.drop_index("ix_voice_calls_load_started", table_name="voice_calls")
    op.drop_table("voice_calls")
    op.drop_index("ix_loads_driver_id", table_name="loads")
    op.drop_index("ix_loads_status_updated_at", table_name="loads")
    op.drop_table("loads")
    op.drop_table("drivers")
    op.drop_table("brokers")
