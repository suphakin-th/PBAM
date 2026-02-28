"""SQLAlchemy ORM models for the document schema."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ARRAY, CheckConstraint, DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from pbam.infrastructure.database.connection import Base


class OcrJobModel(Base):
    __tablename__ = "ocr_jobs"
    __table_args__ = (
        Index("ix_ocr_jobs_user_status", "user_id", "status"),
        Index("ix_ocr_jobs_file_hash", "file_hash"),
        {"schema": "document"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(15),
        CheckConstraint("status IN ('pending','processing','review','committed','failed')"),
        nullable=False,
        default="pending",
    )
    raw_ocr_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StagingTransactionModel(Base):
    __tablename__ = "staging_transactions"
    __table_args__ = (
        Index("ix_staging_ocr_job", "ocr_job_id"),
        Index("ix_staging_user_status", "user_id", "review_status"),
        {"schema": "document"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    ocr_job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_status: Mapped[str] = mapped_column(
        String(15),
        CheckConstraint("review_status IN ('pending','edited','confirmed','discarded')"),
        nullable=False,
        default="pending",
    )
    account_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    category_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    amount_thb: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    original_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    original_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(15, 8), nullable=True)
    transaction_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_date: Mapped[str | None] = mapped_column(Text, nullable=True)  # ISO date string
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=[])
    confidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default={})
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditLogModel(Base):
    __tablename__ = "activity_log"
    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_table_record", "table_name", "record_id"),
        {"schema": "audit"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    schema_name: Mapped[str] = mapped_column(Text, nullable=False)
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(
        String(10),
        CheckConstraint("action IN ('INSERT','UPDATE','DELETE')"),
        nullable=False,
    )
    old_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
