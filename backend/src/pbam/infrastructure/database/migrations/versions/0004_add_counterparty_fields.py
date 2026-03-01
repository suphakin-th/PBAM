"""Add counterparty_ref and counterparty_name to transactions and staging_transactions

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("counterparty_ref", sa.Text(), nullable=True), schema="finance")
    op.add_column("transactions", sa.Column("counterparty_name", sa.Text(), nullable=True), schema="finance")
    op.add_column("staging_transactions", sa.Column("counterparty_ref", sa.Text(), nullable=True), schema="document")
    op.add_column("staging_transactions", sa.Column("counterparty_name", sa.Text(), nullable=True), schema="document")


def downgrade() -> None:
    op.drop_column("transactions", "counterparty_ref", schema="finance")
    op.drop_column("transactions", "counterparty_name", schema="finance")
    op.drop_column("staging_transactions", "counterparty_ref", schema="document")
    op.drop_column("staging_transactions", "counterparty_name", schema="document")
