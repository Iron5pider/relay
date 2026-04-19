"""Unassigned loads — nullable driver_id + driver.last_assigned_at.

Revision ID: 20260419_0002
Revises: 20260419_0001
Create Date: 2026-04-19

Enables the dispatcher consignment-assignment flow: a load can land without a
driver (status='planned', driver_id IS NULL), and the load-balancer scorer
prefers drivers whose `last_assigned_at` is older (freshness tiebreaker).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260419_0002"
down_revision: Union[str, None] = "20260419_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("loads", "driver_id", existing_type=sa.Text(), nullable=True)
    op.add_column(
        "drivers",
        sa.Column("last_assigned_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_column("drivers", "last_assigned_at")
    op.alter_column("loads", "driver_id", existing_type=sa.Text(), nullable=False)
