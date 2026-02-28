"""SQLAlchemy ORM models for the finance schema."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from pbam.infrastructure.database.connection import Base


class AccountModel(Base):
    __tablename__ = "accounts"
    __table_args__ = {"schema": "finance"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("account_type IN ('bank','cash','credit_card','savings','investment')"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="THB")
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default={})
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TransactionCategoryModel(Base):
    __tablename__ = "transaction_categories"
    __table_args__ = (
        Index("ix_tx_categories_user_parent", "user_id", "parent_id", postgresql_where="deleted_at IS NULL"),
        UniqueConstraint("user_id", "parent_id", "name", name="uq_categories_user_parent_name"),
        {"schema": "finance"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category_type: Mapped[str] = mapped_column(
        String(10),
        CheckConstraint("category_type IN ('income','expense','transfer')"),
        nullable=False,
    )
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_date", "user_id", "transaction_date", postgresql_where="deleted_at IS NULL"),
        Index("ix_transactions_account", "account_id", postgresql_where="deleted_at IS NULL"),
        Index("ix_transactions_category", "category_id", postgresql_where="deleted_at IS NULL"),
        {"schema": "finance"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    category_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    amount_thb: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    original_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    original_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(15, 8), nullable=True)
    transaction_type: Mapped[str] = mapped_column(
        String(10),
        CheckConstraint("transaction_type IN ('income','expense','transfer')"),
        nullable=False,
    )
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=[])
    transfer_pair_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    source_document_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TransactionCommentModel(Base):
    __tablename__ = "transaction_comments"
    __table_args__ = (
        Index("ix_tx_comments_transaction", "transaction_id", postgresql_where="deleted_at IS NULL"),
        {"schema": "finance"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    transaction_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TransactionGroupModel(Base):
    __tablename__ = "transaction_groups"
    __table_args__ = {"schema": "finance"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TransactionGroupMemberModel(Base):
    __tablename__ = "transaction_group_members"
    __table_args__ = {"schema": "finance"}

    group_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    transaction_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
