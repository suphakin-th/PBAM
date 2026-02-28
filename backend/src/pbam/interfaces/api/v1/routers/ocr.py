"""OCR router: upload, status, staging review, commit."""
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status

from pbam.application.document.commands import DuplicateFileError, JobNotReadyError
from pbam.interfaces.api.v1.schemas.document import (
    CommitRequest,
    CommitResponse,
    OcrJobResponse,
    StagingRowResponse,
    StagingRowUpdate,
)
from pbam.interfaces.dependencies import CurrentUserId, Facade

router = APIRouter(prefix="/ocr", tags=["ocr"])

_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/upload", response_model=OcrJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_pdf(
    file: UploadFile,
    facade: Facade,
    current_user_id: CurrentUserId,
    background_tasks: BackgroundTasks,
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only PDF files are accepted")

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large (max 20 MB)")

    try:
        job = await facade.submit_ocr_job(current_user_id, file.filename, file_bytes)
    except DuplicateFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "This file has already been imported", "existing_job_id": str(exc)},
        )

    return _job_response(job)


@router.get("", response_model=list[OcrJobResponse])
async def list_jobs(facade: Facade, current_user_id: CurrentUserId):
    jobs = await facade.list_ocr_jobs(current_user_id)
    return [_job_response(j) for j in jobs]


@router.get("/{job_id}", response_model=OcrJobResponse)
async def get_job(job_id: UUID, facade: Facade, current_user_id: CurrentUserId):
    job = await facade.get_ocr_job(job_id, current_user_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _job_response(job)


@router.get("/{job_id}/staging", response_model=list[StagingRowResponse])
async def get_staging(job_id: UUID, facade: Facade, current_user_id: CurrentUserId):
    rows = await facade.get_staging_rows(job_id, current_user_id)
    return [_staging_response(r) for r in rows]


@router.patch("/{job_id}/staging/{staging_id}", response_model=StagingRowResponse)
async def update_staging_row(
    job_id: UUID,
    staging_id: UUID,
    body: StagingRowUpdate,
    facade: Facade,
    current_user_id: CurrentUserId,
):
    row = await facade.update_staging_row(
        staging_id, current_user_id, body.model_dump(exclude_none=True)
    )
    return _staging_response(row)


@router.delete("/{job_id}/staging/{staging_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_staging_row(
    job_id: UUID,
    staging_id: UUID,
    facade: Facade,
    current_user_id: CurrentUserId,
):
    await facade.discard_staging_row(staging_id, current_user_id)


@router.post("/{job_id}/commit", response_model=CommitResponse)
async def commit(
    job_id: UUID,
    body: CommitRequest,
    facade: Facade,
    current_user_id: CurrentUserId,
):
    try:
        count = await facade.commit_staging(job_id, current_user_id, body.default_account_id)
    except JobNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return CommitResponse(committed_count=count, job_id=job_id)


def _job_response(job) -> OcrJobResponse:
    return OcrJobResponse(
        id=job.id,
        original_name=job.original_name,
        file_size_bytes=job.file_size_bytes,
        status=str(job.status),
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
        committed_at=job.committed_at,
        created_at=job.created_at,
    )


def _staging_response(row) -> StagingRowResponse:
    return StagingRowResponse(
        id=row.id,
        ocr_job_id=row.ocr_job_id,
        sort_order=row.sort_order,
        review_status=str(row.review_status),
        account_id=row.account_id,
        category_id=row.category_id,
        amount_thb=row.amount_thb,
        original_amount=row.original_amount,
        original_currency=row.original_currency,
        transaction_type=row.transaction_type,
        payment_method=row.payment_method,
        description=row.description,
        transaction_date=row.transaction_date,
        tags=row.tags,
        confidence=row.confidence,
        raw_text=row.raw_text,
    )
