"""Concrete SQLAlchemy repository implementations for the document context."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pbam.domain.document.entities import OcrJob, OcrJobStatus, StagingReviewStatus, StagingTransaction
from pbam.infrastructure.database.models.document import OcrJobModel, StagingTransactionModel


class OcrJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, job_id: UUID, user_id: UUID) -> OcrJob | None:
        stmt = select(OcrJobModel).where(OcrJobModel.id == job_id, OcrJobModel.user_id == user_id)
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_job(row) if row else None

    async def get_by_file_hash(self, file_hash: str, user_id: UUID) -> OcrJob | None:
        stmt = select(OcrJobModel).where(
            OcrJobModel.file_hash == file_hash,
            OcrJobModel.user_id == user_id,
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_job(row) if row else None

    async def list_by_user(self, user_id: UUID, limit: int = 20, offset: int = 0) -> list[OcrJob]:
        stmt = (
            select(OcrJobModel)
            .where(OcrJobModel.user_id == user_id)
            .order_by(OcrJobModel.created_at.desc())
            .limit(limit).offset(offset)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_job(r) for r in rows]

    async def save(self, job: OcrJob) -> OcrJob:
        existing = await self._s.get(OcrJobModel, job.id)
        if existing:
            existing.status = str(job.status)
            existing.raw_ocr_output = job.raw_ocr_output
            existing.error_message = job.error_message
            existing.started_at = job.started_at
            existing.completed_at = job.completed_at
            existing.committed_at = job.committed_at
        else:
            self._s.add(OcrJobModel(
                id=job.id,
                user_id=job.user_id,
                original_name=job.original_name,
                storage_path=job.storage_path,
                file_hash=job.file_hash,
                file_size_bytes=job.file_size_bytes,
                status=str(job.status),
                created_at=job.created_at,
            ))
        await self._s.flush()
        return job


class StagingTransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_by_job(self, job_id: UUID, user_id: UUID) -> list[StagingTransaction]:
        stmt = (
            select(StagingTransactionModel)
            .where(
                StagingTransactionModel.ocr_job_id == job_id,
                StagingTransactionModel.user_id == user_id,
            )
            .order_by(StagingTransactionModel.sort_order)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_staging(r) for r in rows]

    async def get_by_id(self, staging_id: UUID, user_id: UUID) -> StagingTransaction | None:
        stmt = select(StagingTransactionModel).where(
            StagingTransactionModel.id == staging_id,
            StagingTransactionModel.user_id == user_id,
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_staging(row) if row else None

    async def save(self, staging: StagingTransaction) -> StagingTransaction:
        existing = await self._s.get(StagingTransactionModel, staging.id)
        if existing:
            existing.review_status = str(staging.review_status)
            existing.account_id = staging.account_id
            existing.category_id = staging.category_id
            existing.amount_thb = staging.amount_thb
            existing.original_amount = staging.original_amount
            existing.original_currency = staging.original_currency
            existing.exchange_rate = staging.exchange_rate
            existing.transaction_type = staging.transaction_type
            existing.payment_method = staging.payment_method
            existing.description = staging.description
            existing.transaction_date = staging.transaction_date
            existing.tags = staging.tags
            existing.updated_at = staging.updated_at
        else:
            self._s.add(StagingTransactionModel(
                id=staging.id,
                ocr_job_id=staging.ocr_job_id,
                user_id=staging.user_id,
                sort_order=staging.sort_order,
                review_status=str(staging.review_status),
                account_id=staging.account_id,
                category_id=staging.category_id,
                amount_thb=staging.amount_thb,
                original_amount=staging.original_amount,
                original_currency=staging.original_currency,
                exchange_rate=staging.exchange_rate,
                transaction_type=staging.transaction_type,
                payment_method=staging.payment_method,
                description=staging.description,
                transaction_date=staging.transaction_date,
                tags=staging.tags,
                confidence=staging.confidence,
                raw_text=staging.raw_text,
                created_at=staging.created_at,
                updated_at=staging.updated_at,
            ))
        await self._s.flush()
        return staging

    async def bulk_save(self, stagings: list[StagingTransaction]) -> list[StagingTransaction]:
        for s in stagings:
            await self.save(s)
        return stagings

    async def delete(self, staging_id: UUID, user_id: UUID) -> None:
        model = await self._s.get(StagingTransactionModel, staging_id)
        if model and model.user_id == user_id:
            await self._s.delete(model)
            await self._s.flush()

    async def delete_by_job(self, job_id: UUID) -> None:
        stmt = select(StagingTransactionModel).where(StagingTransactionModel.ocr_job_id == job_id)
        rows = (await self._s.execute(stmt)).scalars().all()
        for row in rows:
            await self._s.delete(row)
        await self._s.flush()


# ── Mappers ───────────────────────────────────────────────────────────────────

def _to_job(m: OcrJobModel) -> OcrJob:
    return OcrJob(
        id=m.id,
        user_id=m.user_id,
        original_name=m.original_name,
        storage_path=m.storage_path,
        file_hash=m.file_hash,
        file_size_bytes=m.file_size_bytes,
        status=OcrJobStatus(m.status),
        raw_ocr_output=m.raw_ocr_output,
        error_message=m.error_message,
        started_at=m.started_at,
        completed_at=m.completed_at,
        committed_at=m.committed_at,
        created_at=m.created_at,
    )


def _to_staging(m: StagingTransactionModel) -> StagingTransaction:
    return StagingTransaction(
        id=m.id,
        ocr_job_id=m.ocr_job_id,
        user_id=m.user_id,
        sort_order=m.sort_order,
        review_status=StagingReviewStatus(m.review_status),
        account_id=m.account_id,
        category_id=m.category_id,
        amount_thb=m.amount_thb,
        original_amount=m.original_amount,
        original_currency=m.original_currency,
        exchange_rate=m.exchange_rate,
        transaction_type=m.transaction_type,
        payment_method=m.payment_method,
        description=m.description,
        transaction_date=m.transaction_date,
        tags=list(m.tags or []),
        confidence=m.confidence or {},
        raw_text=m.raw_text,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )
