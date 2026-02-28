"""Document use-case commands: OCR submit, staging edit, commit."""
from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from pbam.application.finance.commands import create_transaction
from pbam.config import get_settings
from pbam.domain.document.entities import OcrJob, StagingTransaction
from pbam.domain.document.repositories import IOcrJobRepository, IStagingTransactionRepository
from pbam.domain.finance.repositories import ITransactionRepository
from pbam.infrastructure.ocr.processor import OcrResult, process_pdf


class DocumentError(Exception):
    pass


class DuplicateFileError(DocumentError):
    pass


class JobNotReadyError(DocumentError):
    pass


async def submit_ocr_job(
    *,
    user_id: UUID,
    filename: str,
    file_bytes: bytes,
    job_repo: IOcrJobRepository,
    staging_repo: IStagingTransactionRepository,
) -> OcrJob:
    """Save the PDF, queue OCR, and immediately run it synchronously (background task)."""
    settings = get_settings()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Dedup check
    existing = await job_repo.get_by_file_hash(file_hash, user_id)
    if existing is not None:
        raise DuplicateFileError(str(existing.id))

    # Persist file to storage
    storage_dir = settings.storage_path / str(user_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid4().hex}_{filename}"
    storage_path.write_bytes(file_bytes)

    job = OcrJob(
        id=uuid4(),
        user_id=user_id,
        original_name=filename,
        storage_path=str(storage_path),
        file_hash=file_hash,
        file_size_bytes=len(file_bytes),
    )
    job = await job_repo.save(job)

    # Run OCR immediately and create staging rows
    # (In production this would be kicked off as a BackgroundTask — caller wraps this)
    return await _run_ocr_and_stage(job, file_bytes, job_repo, staging_repo)


async def _run_ocr_and_stage(
    job: OcrJob,
    file_bytes: bytes,
    job_repo: IOcrJobRepository,
    staging_repo: IStagingTransactionRepository,
) -> OcrJob:
    """Internal: run OCR on file bytes, create staging rows, update job status."""
    try:
        job.mark_processing()
        await job_repo.save(job)

        result: OcrResult = process_pdf(file_bytes)

        staging_rows = [
            StagingTransaction(
                id=uuid4(),
                ocr_job_id=job.id,
                user_id=job.user_id,
                sort_order=row.sort_order,
                amount_thb=row.amount,
                transaction_type=row.transaction_type,
                payment_method=row.payment_method,
                description=row.description,
                transaction_date=row.transaction_date,
                confidence=row.confidence,
                raw_text=row.raw_text,
            )
            for row in result.rows
        ]
        await staging_repo.bulk_save(staging_rows)

        job.mark_review({"detections": result.raw_output, "row_count": len(result.rows)})
        return await job_repo.save(job)

    except Exception as exc:
        job.mark_failed(str(exc))
        await job_repo.save(job)
        raise


async def update_staging_row(
    *,
    staging_id: UUID,
    user_id: UUID,
    updates: dict,
    staging_repo: IStagingTransactionRepository,
) -> StagingTransaction:
    """User corrects a staging row field by field."""
    row = await staging_repo.get_by_id(staging_id, user_id)
    if row is None:
        raise DocumentError("Staging row not found")

    allowed = {
        "account_id", "category_id", "amount_thb", "original_amount",
        "original_currency", "exchange_rate", "transaction_type", "payment_method",
        "description", "transaction_date", "tags",
    }
    for key, value in updates.items():
        if key in allowed:
            setattr(row, key, value)

    row.mark_edited()
    return await staging_repo.save(row)


async def discard_staging_row(
    *,
    staging_id: UUID,
    user_id: UUID,
    staging_repo: IStagingTransactionRepository,
) -> None:
    """Mark a staging row as discarded (won't be committed)."""
    row = await staging_repo.get_by_id(staging_id, user_id)
    if row is None:
        raise DocumentError("Staging row not found")
    row.discard()
    await staging_repo.save(row)


async def commit_staging(
    *,
    job_id: UUID,
    user_id: UUID,
    default_account_id: UUID,
    job_repo: IOcrJobRepository,
    staging_repo: IStagingTransactionRepository,
    transaction_repo: ITransactionRepository,
) -> int:
    """Atomically move all non-discarded staging rows → finance.transactions.

    Returns the count of committed transactions.
    """
    job = await job_repo.get_by_id(job_id, user_id)
    if job is None:
        raise DocumentError("OCR job not found")
    if job.status != "review":
        raise JobNotReadyError(f"Job is not in review state (current: {job.status})")

    rows = await staging_repo.list_by_job(job_id, user_id)
    committable = [r for r in rows if r.is_committable]

    committed = []
    for row in committable:
        if row.amount_thb is None or row.transaction_type is None:
            continue  # skip incomplete rows

        try:
            tx_date = date.fromisoformat(row.transaction_date) if row.transaction_date else date.today()
        except ValueError:
            tx_date = date.today()

        tx = await create_transaction(
            user_id=user_id,
            account_id=row.account_id or default_account_id,
            amount=row.amount_thb,
            currency=row.original_currency or "THB",
            exchange_rate=row.exchange_rate,
            transaction_type=row.transaction_type,
            payment_method=row.payment_method or "unknown",
            description=row.description or "(imported)",
            transaction_date=tx_date,
            category_id=row.category_id,
            tags=row.tags,
            source_document_id=job_id,
            metadata={"ocr_staging_id": str(row.id)},
            repo=transaction_repo,
        )
        row.confirm()
        await staging_repo.save(row)
        committed.append(tx)

    job.mark_committed()
    await job_repo.save(job)
    return len(committed)
