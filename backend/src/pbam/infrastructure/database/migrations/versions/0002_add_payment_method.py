"""Add payment_method to transactions and staging_transactions

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Supported payment methods for Thai banking context
_PAYMENT_METHODS = (
    'credit_card',      # credit card purchase
    'debit_card',       # debit card purchase
    'qr_code',          # QR code payment (PromptPay QR)
    'promptpay',        # PromptPay phone/ID transfer
    'bank_transfer',    # internet banking transfer
    'digital_wallet',   # Line Pay, TrueMoney, GrabPay, etc.
    'atm',              # ATM cash withdrawal
    'cash',             # cash payment
    'online',           # general online payment
    'subscription',     # recurring subscription
    'unknown',          # fallback
)


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "payment_method",
            sa.String(20),
            nullable=False,
            server_default="unknown",
        ),
        schema="finance",
    )
    op.create_check_constraint(
        "ck_transactions_payment_method",
        "transactions",
        f"payment_method IN ({', '.join(repr(m) for m in _PAYMENT_METHODS)})",
        schema="finance",
    )

    op.add_column(
        "staging_transactions",
        sa.Column("payment_method", sa.String(20), nullable=True),
        schema="document",
    )


def downgrade() -> None:
    op.drop_constraint("ck_transactions_payment_method", "transactions", schema="finance")
    op.drop_column("transactions", "payment_method", schema="finance")
    op.drop_column("staging_transactions", "payment_method", schema="document")
