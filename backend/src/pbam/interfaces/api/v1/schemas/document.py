"""Pydantic v2 schemas for document/OCR endpoints."""
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class OcrJobResponse(BaseModel):
    id: UUID
    original_name: str
    file_size_bytes: int
    status: str
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    committed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StagingRowResponse(BaseModel):
    id: UUID
    ocr_job_id: UUID
    sort_order: int
    review_status: str
    account_id: UUID | None
    category_id: UUID | None
    amount_thb: Decimal | None
    original_amount: Decimal | None
    original_currency: str | None
    transaction_type: str | None
    payment_method: str | None
    description: str | None
    transaction_date: str | None
    tags: list[str]
    confidence: dict[str, Any]
    raw_text: str | None

    model_config = {"from_attributes": True}


class StagingRowUpdate(BaseModel):
    account_id: UUID | None = None
    category_id: UUID | None = None
    amount_thb: Decimal | None = None
    original_amount: Decimal | None = None
    original_currency: str | None = None
    exchange_rate: Decimal | None = None
    transaction_type: str | None = None
    payment_method: str | None = None
    description: str | None = None
    transaction_date: str | None = None
    tags: list[str] | None = None


class CommitRequest(BaseModel):
    default_account_id: UUID


class CommitResponse(BaseModel):
    committed_count: int
    job_id: UUID
