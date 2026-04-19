"""voice_calls.termination_reason column.

Revision ID: 20260419_0004
Revises: 20260419_0003
Create Date: 2026-04-19

ElevenLabs post_call payloads carry `data.metadata.termination_reason` —
useful for the dispatcher's Calls screen ("why did this call end?"). We
already persist `analysis_json` JSONB which captures most things, but a
dedicated column makes the field queryable + avoids JSON digging in list
views.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260419_0004"
down_revision: Union[str, None] = "20260419_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("voice_calls", sa.Column("termination_reason", sa.Text()))


def downgrade() -> None:
    op.drop_column("voice_calls", "termination_reason")
