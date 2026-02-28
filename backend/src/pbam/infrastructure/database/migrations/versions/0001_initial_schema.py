"""Initial schema — identity, finance, document, audit

Revision ID: 0001
Revises:
Create Date: 2026-02-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ──────────────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── Schemas ──────────────────────────────────────────────────────────────
    op.execute("CREATE SCHEMA IF NOT EXISTS identity")
    op.execute("CREATE SCHEMA IF NOT EXISTS finance")
    op.execute("CREATE SCHEMA IF NOT EXISTS document")
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")

    # ── identity.users ───────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("biometric_public_key", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="identity",
    )
    op.create_index("ix_users_email_active", "users", ["email"], schema="identity",
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # ── identity.user_sessions ───────────────────────────────────────────────
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jti_hash", sa.Text, nullable=False, unique=True),
        sa.Column("device_fingerprint", sa.Text, nullable=True),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["identity.users.id"], ondelete="CASCADE"),
        schema="identity",
    )
    op.create_index("ix_user_sessions_user_expires", "user_sessions", ["user_id", "expires_at"],
                    schema="identity", postgresql_where=sa.text("revoked_at IS NULL"))

    # ── finance.accounts ─────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'THB'")),
        sa.Column("initial_balance", sa.Numeric(15, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("account_type IN ('bank','cash','credit_card','savings','investment')", name="ck_accounts_type"),
        sa.ForeignKeyConstraint(["user_id"], ["identity.users.id"], ondelete="CASCADE"),
        schema="finance",
    )

    # ── finance.transaction_categories ──────────────────────────────────────
    op.create_table(
        "transaction_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("category_type", sa.String(10), nullable=False),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("icon", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("category_type IN ('income','expense','transfer')", name="ck_category_type"),
        sa.ForeignKeyConstraint(["user_id"], ["identity.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["finance.transaction_categories.id"], ondelete="SET NULL"),
        schema="finance",
    )
    op.create_index("ix_tx_categories_user_parent", "transaction_categories", ["user_id", "parent_id"],
                    schema="finance", postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_unique_constraint(
        "uq_categories_user_parent_name",
        "transaction_categories",
        ["user_id", "parent_id", "name"],
        schema="finance",
    )

    # ── finance.transactions ─────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount_thb", sa.Numeric(15, 4), nullable=False),
        sa.Column("original_amount", sa.Numeric(15, 4), nullable=True),
        sa.Column("original_currency", sa.String(3), nullable=True),
        sa.Column("exchange_rate", sa.Numeric(15, 8), nullable=True),
        sa.Column("transaction_type", sa.String(10), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_recurring", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("transaction_type IN ('income','expense','transfer')", name="ck_transaction_type"),
        sa.ForeignKeyConstraint(["user_id"], ["identity.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["finance.accounts.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["finance.transaction_categories.id"], ondelete="SET NULL"),
        schema="finance",
    )
    op.create_index("ix_transactions_user_date", "transactions", ["user_id", "transaction_date"],
                    schema="finance", postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_transactions_account", "transactions", ["account_id"],
                    schema="finance", postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_transactions_category", "transactions", ["category_id"],
                    schema="finance", postgresql_where=sa.text("deleted_at IS NULL"))

    # ── finance.transaction_comments ─────────────────────────────────────────
    op.create_table(
        "transaction_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["transaction_id"], ["finance.transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["identity.users.id"], ondelete="CASCADE"),
        schema="finance",
    )
    op.create_index("ix_tx_comments_transaction", "transaction_comments", ["transaction_id"],
                    schema="finance", postgresql_where=sa.text("deleted_at IS NULL"))

    # ── finance.transaction_groups ───────────────────────────────────────────
    op.create_table(
        "transaction_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["identity.users.id"], ondelete="CASCADE"),
        schema="finance",
    )

    # ── finance.transaction_group_members ────────────────────────────────────
    op.create_table(
        "transaction_group_members",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("group_id", "transaction_id"),
        sa.ForeignKeyConstraint(["group_id"], ["finance.transaction_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["finance.transactions.id"], ondelete="CASCADE"),
        schema="finance",
    )

    # ── document.ocr_jobs ────────────────────────────────────────────────────
    op.create_table(
        "ocr_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_name", sa.Text, nullable=False),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("file_hash", sa.Text, nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("status", sa.String(15), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("raw_ocr_output", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending','processing','review','committed','failed')", name="ck_ocr_status"),
        sa.ForeignKeyConstraint(["user_id"], ["identity.users.id"], ondelete="CASCADE"),
        schema="document",
    )
    op.create_index("ix_ocr_jobs_user_status", "ocr_jobs", ["user_id", "status"], schema="document")
    op.create_index("ix_ocr_jobs_file_hash", "ocr_jobs", ["file_hash"], schema="document")

    # ── document.staging_transactions ────────────────────────────────────────
    op.create_table(
        "staging_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ocr_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("review_status", sa.String(15), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount_thb", sa.Numeric(15, 4), nullable=True),
        sa.Column("original_amount", sa.Numeric(15, 4), nullable=True),
        sa.Column("original_currency", sa.String(3), nullable=True),
        sa.Column("exchange_rate", sa.Numeric(15, 8), nullable=True),
        sa.Column("transaction_type", sa.String(10), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("transaction_date", sa.Text, nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("confidence", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("review_status IN ('pending','edited','confirmed','discarded')", name="ck_staging_status"),
        sa.ForeignKeyConstraint(["ocr_job_id"], ["document.ocr_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["identity.users.id"], ondelete="CASCADE"),
        schema="document",
    )
    op.create_index("ix_staging_ocr_job", "staging_transactions", ["ocr_job_id"], schema="document")
    op.create_index("ix_staging_user_status", "staging_transactions", ["user_id", "review_status"], schema="document")

    # ── audit.activity_log ───────────────────────────────────────────────────
    op.create_table(
        "activity_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("schema_name", sa.Text, nullable=False),
        sa.Column("table_name", sa.Text, nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("old_data", postgresql.JSONB, nullable=True),
        sa.Column("new_data", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("action IN ('INSERT','UPDATE','DELETE')", name="ck_audit_action"),
        schema="audit",
    )
    op.create_index("ix_audit_user_created", "activity_log", ["user_id", "created_at"], schema="audit")
    op.create_index("ix_audit_table_record", "activity_log", ["table_name", "record_id"], schema="audit")

    # ── Row Level Security ────────────────────────────────────────────────────
    for schema, table in [
        ("identity", "users"),
        ("identity", "user_sessions"),
        ("finance", "accounts"),
        ("finance", "transaction_categories"),
        ("finance", "transactions"),
        ("finance", "transaction_comments"),
        ("finance", "transaction_groups"),
        ("finance", "transaction_group_members"),
        ("document", "ocr_jobs"),
        ("document", "staging_transactions"),
    ]:
        op.execute(f'ALTER TABLE "{schema}"."{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    # Drop in reverse FK order
    for schema, table in [
        ("document", "staging_transactions"),
        ("document", "ocr_jobs"),
        ("finance", "transaction_group_members"),
        ("finance", "transaction_groups"),
        ("finance", "transaction_comments"),
        ("finance", "transactions"),
        ("finance", "transaction_categories"),
        ("finance", "accounts"),
        ("identity", "user_sessions"),
        ("identity", "users"),
        ("audit", "activity_log"),
    ]:
        op.drop_table(table, schema=schema)

    op.execute("DROP SCHEMA IF EXISTS audit CASCADE")
    op.execute("DROP SCHEMA IF EXISTS document CASCADE")
    op.execute("DROP SCHEMA IF EXISTS finance CASCADE")
    op.execute("DROP SCHEMA IF EXISTS identity CASCADE")
