"""Reaboard REST API Endpoints.

Implements OpenAPI 3.1 specification for streaming uploads, SSE events,
job execution, reports, and signed downloads.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from apps.api.src.core.config import settings
from apps.api.src.core.filetype import (
    FileTypeError,
    detect_file_type,
)
from apps.api.src.core.security import (
    format_content_disposition,
    sanitize_filename,
    verify_download_signature,
)
from apps.api.src.schemas.schemas import (
    ErrorCode,
    ErrorDetail,
    ErrorEnvelope,
    JobStatus,
    RemovalOptions,
)
from apps.api.src.services.job_service import InvalidStateTransitionError, job_service

router = APIRouter(prefix="/api/v1")
limiter = Limiter(key_func=get_remote_address)


def _validate_uuid(val: str) -> str:
    """Validate that path parameter is a valid UUID4 string."""
    try:
        return str(uuid.UUID(val))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message=f"Invalid job identifier: '{val}'")
            ).model_dump(by_alias=True),
        )


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{settings.rate_limit_uploads_per_hour}/hour")
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    batch_id: str | None = Form(None),
):
    """Upload a file, check magic bytes, and stage in ephemeral storage with rate limiting."""
    client_name = sanitize_filename(file.filename or "uploaded_file")

    # Read first 64 KB for comprehensive magic byte verification
    header = await file.read(65536)
    if not header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.UNSUPPORTED_TYPE, message="Empty file payload")
            ).model_dump(by_alias=True),
        )

    try:
        det = detect_file_type(header, client_name)
        detected_type = det.normalized_type
        detected_mime = det.mime_type
    except FileTypeError as e:
        err_code = ErrorCode.TYPE_MISMATCH if e.code == "TYPE_MISMATCH" else ErrorCode.UNSUPPORTED_TYPE
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code=err_code,
                    message=str(e),
                    hint=e.hint or "Supported formats: MP4, MOV, MKV, WebM, AVI, JPEG, PNG, WebP, HEIC, TIFF, PDF, DOCX, XLSX, PPTX, MP3, FLAC, OGG, WAV, M4A.",
                )
            ).model_dump(by_alias=True),
        )

    # Generate job ID and stage directly into storage
    job_id = str(uuid.uuid4())
    job_dir = job_service.storage.get_job_dir(job_id)
    target_path = job_dir / f"in.{detected_type}"

    hasher = hashlib.sha256()
    hasher.update(header)
    total_bytes = len(header)

    with open(target_path, "wb") as f:
        f.write(header)
        while chunk := await file.read(65536):
            total_bytes += len(chunk)
            if total_bytes > settings.max_upload_bytes:
                f.close()
                target_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=ErrorEnvelope(
                        error=ErrorDetail(
                            code=ErrorCode.FILE_TOO_LARGE,
                            message=f"File exceeds maximum allowed size of {settings.max_upload_mb} MB",
                        )
                    ).model_dump(by_alias=True),
                )
            hasher.update(chunk)
            f.write(chunk)

    sha256_hex = hasher.hexdigest()

    # Register staged job
    job = job_service.create_job(
        original_filename=client_name,
        detected_mime=detected_mime,
        detected_type=detected_type,
        size_bytes=total_bytes,
        sha256=sha256_hex,
        job_id=job_id,
        batch_id=batch_id,
    )

    return {
        "jobId": job.id,
        "detectedType": detected_type,
        "detectedMime": detected_mime,
        "size": total_bytes,
        "sha256": sha256_hex,
    }


@router.get("/jobs/{id}")
async def get_job(id: str):
    """Retrieve job status, progress percentage, and results."""
    clean_id = _validate_uuid(id)
    job = await job_service.get_job_async(clean_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found or expired")
            ).model_dump(by_alias=True),
        )
    return job.model_dump(by_alias=True)


@router.post("/jobs/{id}/view", status_code=status.HTTP_202_ACCEPTED)
async def start_view_job(id: str):
    """Enqueue metadata inspection (View mode). Idempotent if already queued/analyzing."""
    clean_id = _validate_uuid(id)
    job = await job_service.get_job_async(clean_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found")
            ).model_dump(by_alias=True),
        )

    # Idempotent check
    if job.status in (JobStatus.QUEUED, JobStatus.ANALYZING, JobStatus.COMPLETED):
        return {"jobId": clean_id, "status": job.status.value}

    try:
        await job_service.update_stage(clean_id, JobStatus.QUEUED, "queued", 10)
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.INVALID_STATE, message=str(e))
            ).model_dump(by_alias=True),
        )

    await job_service.enqueue_view_job(clean_id)
    return {"jobId": clean_id, "status": "queued"}


@router.post("/jobs/{id}/remove", status_code=status.HTTP_202_ACCEPTED)
async def start_remove_job(id: str, options: RemovalOptions | None = None):
    """Enqueue lossless metadata removal and verification (Remove mode). Idempotent."""
    clean_id = _validate_uuid(id)
    job = await job_service.get_job_async(clean_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found")
            ).model_dump(by_alias=True),
        )

    # Idempotent check
    if job.status in (
        JobStatus.QUEUED,
        JobStatus.ANALYZING,
        JobStatus.CLEANING,
        JobStatus.VERIFYING,
        JobStatus.COMPLETED,
        JobStatus.COMPLETED_WITH_WARNINGS,
    ):
        return {"jobId": clean_id, "status": job.status.value}

    try:
        await job_service.update_stage(clean_id, JobStatus.QUEUED, "queued", 10)
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.INVALID_STATE, message=str(e))
            ).model_dump(by_alias=True),
        )

    await job_service.enqueue_remove_job(clean_id, options)
    return {"jobId": clean_id, "status": "queued"}


@router.get("/jobs/{id}/events")
async def get_job_events(id: str):
    """Realtime Server-Sent Events (SSE) progress stream."""
    clean_id = _validate_uuid(id)
    job = await job_service.get_job_async(clean_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found")
            ).model_dump(by_alias=True),
        )

    return StreamingResponse(
        job_service.subscribe_events(clean_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/jobs/{id}/report")
async def get_job_report(id: str):
    """Retrieve structured metadata report or verified removal diff report."""
    clean_id = _validate_uuid(id)
    report = await job_service.get_report_async(clean_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Report not yet ready or job not found")
            ).model_dump(by_alias=True),
        )
    return report.model_dump(by_alias=True)


@router.get("/jobs/{id}/download")
async def download_file(
    id: str,
    signature: str = Query(...),
    expires: int = Query(...),
    dl_name: str | None = Query(None),
):
    """Stream cleaned output file with HMAC signature verification and RFC 6266 headers."""
    clean_id = _validate_uuid(id)

    # Verify download signature bound to job_id and filename
    if not verify_download_signature(clean_id, signature, expires, filename=dl_name or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.INVALID_SIGNATURE, message="Invalid or expired download signature")
            ).model_dump(by_alias=True),
        )

    job = await job_service.get_job_async(clean_id)
    if not job or not job.file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found or expired")
            ).model_dump(by_alias=True),
        )

    job_dir = job_service.storage.get_job_dir(clean_id)
    output_path = job_dir / f"out.{job.file_info.detected_type}"

    if not output_path.exists():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code=ErrorCode.JOB_NOT_FOUND,
                    message="Cleaned file has been purged from ephemeral storage",
                )
            ).model_dump(by_alias=True),
        )

    orig_stem = Path(job.file_info.original_filename).stem
    download_filename = dl_name or f"{orig_stem}_reaboard.{job.file_info.detected_type}"
    download_filename = sanitize_filename(download_filename)

    return FileResponse(
        path=output_path,
        media_type=job.file_info.detected_mime,
        headers={
            "Content-Disposition": format_content_disposition(download_filename),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/jobs/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(id: str):
    """Immediately purge job and delete all files from ephemeral storage."""
    clean_id = _validate_uuid(id)
    deleted = job_service.delete_job(clean_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found")
            ).model_dump(by_alias=True),
        )
    return None
