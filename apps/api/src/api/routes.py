"""Reaboard REST API Endpoints.

Implements OpenAPI 3.1 specification for streaming uploads, SSE events,
job execution, reports, and signed downloads.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from apps.api.src.core.security import sanitize_filename, verify_download_signature
from apps.api.src.schemas.schemas import (
    ErrorCode,
    ErrorDetail,
    ErrorEnvelope,
    Job,
    JobStatus,
    RemovalOptions,
)
from apps.api.src.services.job_service import job_service


router = APIRouter(prefix="/api/v1")


def detect_magic_type(header: bytes, filename: str) -> tuple[str, str]:
    """Detect file type and MIME type from initial header bytes (Magic Bytes).

    Returns:
        (detected_type, detected_mime)
    """
    if len(header) < 4:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code=ErrorCode.UNSUPPORTED_TYPE,
                    message="File is too small to identify format signature.",
                )
            ).model_dump(),
        )

    # 1. JPEG
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg", "image/jpeg"

    # 2. PNG
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"

    # 3. WebP & AVI (RIFF containers)
    if header.startswith(b"RIFF") and len(header) >= 12:
        riff_type = header[8:12]
        if riff_type == b"WEBP":
            return "webp", "image/webp"
        if riff_type == b"AVI ":
            return "avi", "video/x-msvideo"
        if riff_type == b"WAVE":
            return "wav", "audio/wav"

    # 4. MP4 / MOV / M4V (ISO Base Media File Format)
    if len(header) >= 8 and header[4:8] == b"ftyp":
        major_brand = header[8:12] if len(header) >= 12 else b""
        if major_brand == b"qt  ":
            return "mov", "video/quicktime"
        if major_brand == b"M4A ":
            return "m4a", "audio/mp4"
        return "mp4", "video/mp4"

    # 5. Matroska / WebM (EBML)
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        ext = Path(filename).suffix.lower()
        if ext == ".webm":
            return "webm", "video/webm"
        return "mkv", "video/x-matroska"

    # 6. PDF
    if header.startswith(b"%PDF-"):
        return "pdf", "application/pdf"

    # 7. Office / ZIP (PKZip)
    if header.startswith(b"PK\x03\x04"):
        ext = Path(filename).suffix.lower()
        if ext == ".docx":
            return "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if ext == ".xlsx":
            return "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if ext == ".pptx":
            return "pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        return "zip", "application/zip"

    # 8. Audio
    if header.startswith(b"ID3") or header.startswith(b"\xff\xfb") or header.startswith(b"\xff\xf3"):
        return "mp3", "audio/mpeg"
    if header.startswith(b"fLaC"):
        return "flac", "audio/flac"
    if header.startswith(b"OggS"):
        return "ogg", "audio/ogg"

    # Block hostile executables disguised as media
    if header.startswith(b"MZ") or header.startswith(b"\x7fELF"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code=ErrorCode.TYPE_MISMATCH,
                    message="Executable files disguised as media are strictly rejected.",
                    hint="Ensure you are uploading a valid image, video, or document.",
                )
            ).model_dump(),
        )

    # Check for text/scripts or executable payloads disguised with media extensions
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in ("mp4", "mov", "m4v", "mkv", "webm", "avi", "jpeg", "jpg", "png", "webp", "pdf"):
        # These formats MUST have matched their magic bytes above. If they reach here, it is a mismatch.
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code=ErrorCode.TYPE_MISMATCH,
                    message=f"File extension '.{ext}' does not match detected header contents.",
                    hint="Ensure the file is not corrupted or renamed from another format.",
                )
            ).model_dump(),
        )

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=ErrorEnvelope(
            error=ErrorDetail(
                code=ErrorCode.UNSUPPORTED_TYPE,
                message=f"Unsupported file signature for '{filename}'.",
                hint="Supported formats: MP4, MOV, MKV, WebM, AVI, JPEG, PNG, WebP, HEIC, PDF, MP3.",
            )
        ).model_dump(),
    )


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(
    file: UploadFile = File(...),
    batch_id: str | None = Form(None),
):
    """Upload a file, check magic bytes, and stage in ephemeral storage."""
    client_name = sanitize_filename(file.filename or "uploaded_file")

    # Read first 16 bytes for magic byte verification
    header = await file.read(16)
    if not header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.UNSUPPORTED_TYPE, message="Empty file payload")
            ).model_dump(),
        )

    detected_type, detected_mime = detect_magic_type(header, client_name)

    # Generate job ID first to set up directory
    import uuid
    job_id = str(uuid.uuid4())
    job_dir = job_service.storage.get_job_dir(job_id)
    target_path = job_dir / f"in.{detected_type}"

    # Stream remaining file chunks to disk
    import hashlib
    hasher = hashlib.sha256()
    hasher.update(header)
    total_bytes = len(header)

    with open(target_path, "wb") as f:
        f.write(header)
        while chunk := await file.read(65536):
            total_bytes += len(chunk)
            if total_bytes > 500 * 1024 * 1024:  # 500 MB hard cap
                f.close()
                target_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=ErrorEnvelope(
                        error=ErrorDetail(code=ErrorCode.FILE_TOO_LARGE, message="File exceeds 500 MB limit")
                    ).model_dump(),
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
        batch_id=batch_id,
    )
    # Align ID with generated directory
    job_service._jobs.pop(job.id, None)
    job.id = job_id
    job_service._jobs[job_id] = job

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
    job = job_service.get_job(id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found or expired")
            ).model_dump(),
        )
    return job.model_dump()


@router.post("/jobs/{id}/view", status_code=status.HTTP_202_ACCEPTED)
async def start_view_job(id: str):
    """Enqueue metadata inspection (View mode)."""
    job = job_service.get_job(id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found")
            ).model_dump(),
        )

    # Trigger inspection asynchronously
    asyncio.create_task(job_service.execute_view_job(id))
    return {"jobId": id, "status": "queued"}


@router.post("/jobs/{id}/remove", status_code=status.HTTP_202_ACCEPTED)
async def start_remove_job(id: str, options: RemovalOptions | None = None):
    """Enqueue lossless metadata removal and verification (Remove mode)."""
    job = job_service.get_job(id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found")
            ).model_dump(),
        )

    asyncio.create_task(job_service.execute_remove_job(id, options))
    return {"jobId": id, "status": "queued"}


@router.get("/jobs/{id}/events")
async def get_job_events(id: str):
    """Realtime Server-Sent Events (SSE) progress stream."""
    job = job_service.get_job(id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found")
            ).model_dump(),
        )

    return StreamingResponse(
        job_service.subscribe_events(id),
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
    report = job_service.get_report(id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Report not yet ready or job not found")
            ).model_dump(),
        )
    return report.model_dump()


@router.get("/jobs/{id}/download")
async def download_file(
    id: str,
    signature: str = Query(...),
    expires: int = Query(...),
    dl_name: str | None = Query(None),
):
    """Stream cleaned output file with HMAC signature verification and RFC 6266 headers."""
    if not verify_download_signature(id, signature, expires):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.INVALID_SIGNATURE, message="Invalid or expired download signature")
            ).model_dump(),
        )

    job = job_service.get_job(id)
    if not job or not job.file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found or expired")
            ).model_dump(),
        )

    job_dir = job_service.storage.get_job_dir(id)
    output_path = job_dir / f"out.{job.file_info.detected_type}"

    if not output_path.exists():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Cleaned file has been purged from ephemeral storage")
            ).model_dump(),
        )

    orig_stem = Path(job.file_info.original_filename).stem
    download_filename = dl_name or f"{orig_stem}_reaboard.{job.file_info.detected_type}"
    download_filename = sanitize_filename(download_filename)

    return FileResponse(
        path=output_path,
        media_type=job.file_info.detected_mime,
        filename=download_filename,
        headers={
            "Content-Disposition": f'attachment; filename="{download_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/jobs/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(id: str):
    """Immediately purge job and delete all files from ephemeral storage."""
    deleted = job_service.delete_job(id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=ErrorCode.JOB_NOT_FOUND, message="Job not found")
            ).model_dump(),
        )
    return None
