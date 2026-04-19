"""POD fields on loads + sent_at/sent_to_email on invoices.

Revision ID: 20260419_0003
Revises: 20260419_0002
Create Date: 2026-04-19

Adds the columns the dashboard billing/POD flow needs:
- loads.pod_url, pod_signed_by, pod_received_at
- invoices.sent_at, invoices.sent_to_email
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260419_0003"
down_revision: Union[str, None] = "20260419_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("loads", sa.Column("pod_url", sa.Text()))
    op.add_column("loads", sa.Column("pod_signed_by", sa.Text()))
    op.add_column("loads", sa.Column("pod_received_at", sa.DateTime(timezone=True)))
    op.add_column("invoices", sa.Column("sent_at", sa.DateTime(timezone=True)))
    op.add_column("invoices", sa.Column("sent_to_email", sa.Text()))


def downgrade() -> None:
    op.drop_column("invoices", "sent_to_email")
    op.drop_column("invoices", "sent_at")
    op.drop_column("loads", "pod_received_at")
    op.drop_column("loads", "pod_signed_by")
    op.drop_column("loads", "pod_url")
