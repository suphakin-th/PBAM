"""Document use-case queries."""
from uuid import UUID

from pbam.domain.document.entities import OcrJob, StagingTransaction
from pbam.domain.document.repositories import IOcrJobRepository, IStagingTransactionRepository


async def get_ocr_job(job_id: UUID, user_id: UUID, repo: IOcrJobRepository) -> OcrJob | None:
    return await repo.get_by_id(job_id, user_id)


async def list_ocr_jobs(user_id: UUID, repo: IOcrJobRepository) -> list[OcrJob]:
    return await repo.list_by_user(user_id)


async def get_staging_rows(
    job_id: UUID, user_id: UUID, repo: IStagingTransactionRepository
) -> list[StagingTransaction]:
    return await repo.list_by_job(job_id, user_id)
