"""Domain entities for the Document bounded context."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class OcrJobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    REVIEW = "review"       # staging rows created, user reviewing
    COMMITTED = "committed" # user confirmed, data in finance.transactions
    FAILED = "failed"


class StagingReviewStatus(StrEnum):
    PENDING = "pending"
    EDITED = "edited"
    CONFIRMED = "confirmed"
    DISCARDED = "discarded"


@dataclass
class OcrJob:
    id: UUID
    user_id: UUID
    original_name: str
    storage_path: str
    file_hash: str
    file_size_bytes: int
    status: OcrJobStatus = OcrJobStatus.PENDING
    raw_ocr_output: dict | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    committed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def mark_processing(self) -> None:
        self.status = OcrJobStatus.PROCESSING
        self.started_at = datetime.utcnow()

    def mark_review(self, raw_ocr_output: dict) -> None:
        self.status = OcrJobStatus.REVIEW
        self.raw_ocr_output = raw_ocr_output
        self.completed_at = datetime.utcnow()

    def mark_committed(self) -> None:
        self.status = OcrJobStatus.COMMITTED
        self.committed_at = datetime.utcnow()

    def mark_failed(self, error: str) -> None:
        self.status = OcrJobStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.utcnow()


@dataclass
class StagingTransaction:
    """An OCR-extracted transaction row awaiting user review/correction."""
    id: UUID
    ocr_job_id: UUID
    user_id: UUID
    sort_order: int = 0
    review_status: StagingReviewStatus = StagingReviewStatus.PENDING
    # Editable fields — user corrects these
    account_id: UUID | None = None
    category_id: UUID | None = None
    amount_thb: Decimal | None = None
    original_amount: Decimal | None = None
    original_currency: str | None = None
    exchange_rate: Decimal | None = None
    transaction_type: str | None = None
    payment_method: str | None = None
    counterparty_ref: str | None = None
    counterparty_name: str | None = None
    description: str | None = None
    transaction_date: str | None = None  # ISO date string
    tags: list[str] = field(default_factory=list)
    # OCR metadata
    confidence: dict = field(default_factory=dict)  # {field: 0.0–1.0}
    raw_text: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def mark_edited(self) -> None:
        self.review_status = StagingReviewStatus.EDITED
        self.updated_at = datetime.utcnow()

    def discard(self) -> None:
        self.review_status = StagingReviewStatus.DISCARDED
        self.updated_at = datetime.utcnow()

    def confirm(self) -> None:
        self.review_status = StagingReviewStatus.CONFIRMED
        self.updated_at = datetime.utcnow()

    @property
    def is_committable(self) -> bool:
        return self.review_status != StagingReviewStatus.DISCARDED
