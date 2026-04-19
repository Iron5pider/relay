"""Tools-contract tables — 6 new + voice_calls extensions.

Revision ID: 20260419_0001
Revises: 20260419_0000
Create Date: 2026-04-19

Per `API_DOCS/tools_contract.md` §10. Additive to the initial schema.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260419_0001"
down_revision: Union[str, None] = "20260419_0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- voice_calls additive columns ---
    op.add_column(
        "voice_calls",
        sa.Column("conversation_id", sa.Text()),
    )
    op.create_unique_constraint(
        "uq_voice_calls_conversation_id", "voice_calls", ["conversation_id"]
    )
    op.add_column("voice_calls", sa.Column("agent_id", sa.Text()))
    op.add_column(
        "voice_calls",
        sa.Column(
            "driver_id",
            sa.Text(),
            sa.ForeignKey("drivers.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("voice_calls", sa.Column("trigger_reason", sa.Text()))
    op.add_column(
        "voice_calls",
        sa.Column(
            "call_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'dialing'"),
        ),
    )
    op.add_column(
        "voice_calls",
        sa.Column(
            "analysis_json",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("ix_voice_calls_driver_id", "voice_calls", ["driver_id"])

    # --- New tables ---
    op.create_table(
        "incidents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "driver_id",
            sa.Text(),
            sa.ForeignKey("drivers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "call_id",
            sa.Text(),
            sa.ForeignKey("voice_calls.id", ondelete="SET NULL"),
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "detention_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "call_id",
            sa.Text(),
            sa.ForeignKey("voice_calls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "load_id",
            sa.Text(),
            sa.ForeignKey("loads.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("ap_contact_name", sa.Text()),
        sa.Column("ap_contact_method", sa.Text()),
        sa.Column("ap_contact_detail", sa.Text()),
        sa.Column("supervisor_name", sa.Text()),
        sa.Column("committed_to_pay", sa.Boolean(), nullable=False),
        sa.Column("detention_hours_confirmed", sa.Numeric(6, 2)),
        sa.Column("notes", sa.Text()),
        sa.Column("escalation_step_reached", sa.Integer()),
        sa.Column("contact_attempted", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "invoices",
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
        sa.Column("pdf_url", sa.Text()),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'ready_for_review'"),
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "dispatcher_notifications",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("urgency", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "driver_id",
            sa.Text(),
            sa.ForeignKey("drivers.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "load_id",
            sa.Text(),
            sa.ForeignKey("loads.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "call_id",
            sa.Text(),
            sa.ForeignKey("voice_calls.id", ondelete="SET NULL"),
        ),
        sa.Column("ack_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "dispatcher_tasks",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("priority", sa.Text(), nullable=False, server_default=sa.text("'med'")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column(
            "related_call_id",
            sa.Text(),
            sa.ForeignKey("voice_calls.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "transcript_snapshots",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "call_id",
            sa.Text(),
            sa.ForeignKey("voice_calls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key_quote", sa.Text(), nullable=False),
        sa.Column("quote_type", sa.Text(), nullable=False),
        sa.Column("timestamp_in_call", sa.Numeric(8, 2)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("transcript_snapshots")
    op.drop_table("dispatcher_tasks")
    op.drop_table("dispatcher_notifications")
    op.drop_table("invoices")
    op.drop_table("detention_events")
    op.drop_table("incidents")

    op.drop_index("ix_voice_calls_driver_id", table_name="voice_calls")
    op.drop_column("voice_calls", "analysis_json")
    op.drop_column("voice_calls", "call_status")
    op.drop_column("voice_calls", "trigger_reason")
    op.drop_column("voice_calls", "driver_id")
    op.drop_column("voice_calls", "agent_id")
    op.drop_constraint("uq_voice_calls_conversation_id", "voice_calls", type_="unique")
    op.drop_column("voice_calls", "conversation_id")
