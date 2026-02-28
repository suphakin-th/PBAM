"""Add transfer_pair_id to finance.transactions

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "transfer_pair_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema="finance",
    )


def downgrade() -> None:
    op.drop_column("transactions", "transfer_pair_id", schema="finance")
