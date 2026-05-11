"""Add audit_log table for compliance.

Revision ID: 002_audit_log
Revises: 001_initial
Create Date: 2026-05-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_audit_log"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("actor_id", sa.Integer),
        sa.Column("target_id", sa.Integer),
        sa.Column("details", sa.Text),
        sa.Column("ip_address", sa.Text),
        sa.Column("correlation_id", sa.Text),
        sa.Column("chain_hash", sa.Text, nullable=False),
    )

    op.create_index("idx_audit_event_type", "audit_log", ["event_type"])
    op.create_index("idx_audit_actor_id", "audit_log", ["actor_id"])
    op.create_index("idx_audit_timestamp", "audit_log", ["timestamp"])


def downgrade() -> None:
    op.drop_index("idx_audit_timestamp", table_name="audit_log")
    op.drop_index("idx_audit_actor_id", table_name="audit_log")
    op.drop_index("idx_audit_event_type", table_name="audit_log")
    op.drop_table("audit_log")
