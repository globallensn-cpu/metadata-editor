"""Reaboard Job Service and State Manager.

Orchestrates job lifecycle transitions, event streaming (SSE),
and metadata inspection / removal execution.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from apps.api.src.core.security import sign_download_url
from apps.api.src.core.storage import LocalStorageBackend, StorageBackend
from apps.api.src.schemas.schemas import (
    CleaningMethod,
    ErrorCode,
    ErrorDetail,
    FileInfo,
    Job,
    JobAction,
    JobStatus,
    MetadataReport,
    RemovalOptions,
    RemovalReport,
)
from apps.worker.src.engine.pipelines.image import clean_image
from apps.worker.src.engine.pipelines.video import clean_video_lossless
from apps.worker.src.engine.strategy import StrategySelectionError, select_cleaning_strategy
from apps.worker.src.engine.verify import (
    build_metadata_report,
    build_removal_report,
    compute_stream_md5,
    extract_unified_metadata,
    verify_playback,
)


# Default job retention: 60 minutes
DEFAULT_JOB_RETENTION_MINUTES = 60


class JobService:
    """Manages job records, state machine transitions, and execution."""

    def __init__(self, storage: StorageBackend | None = None) -> None:
        self.storage = storage or LocalStorageBackend()
        # Ephemeral in-memory store for MVP / dev mode, easily backed by Redis
        self._jobs: dict[str, Job] = {}
        self._reports: dict[str, MetadataReport | RemovalReport] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def get_report(self, job_id: str) -> MetadataReport | RemovalReport | None:
        return self._reports.get(job_id)

    def create_job(
        self,
        original_filename: str,
        detected_mime: str,
        detected_type: str,
        size_bytes: int,
        sha256: str,
        batch_id: str | None = None,
    ) -> Job:
        """Create a new staged job record in 'uploaded' state."""
        job_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=DEFAULT_JOB_RETENTION_MINUTES)

        file_info = FileInfo(
            original_filename=original_filename,
            detected_mime=detected_mime,
            detected_type=detected_type,
            size_bytes=size_bytes,
            sha256=sha256,
        )

        job = Job(
            id=job_id,
            batch_id=batch_id,
            status=JobStatus.UPLOADED,
            file_info=file_info,
            progress_percent=0,
            current_stage="uploaded",
            created_at=now,
            expires_at=expires_at,
        )
        self._jobs[job_id] = job
        return job

    async def update_stage(self, job_id: str, status: JobStatus, stage_name: str, progress: int) -> None:
        """Update job stage and broadcast update to all active SSE subscribers."""
        job = self._jobs.get(job_id)
        if not job:
            return

        job.status = status
        job.current_stage = stage_name
        job.progress_percent = progress

        # Broadcast via SSE
        event_payload = {
            "jobId": job_id,
            "status": status.value,
            "stage": stage_name,
            "progress": progress,
        }
        await self._broadcast_event(job_id, event_payload)

    async def subscribe_events(self, job_id: str) -> AsyncGenerator[str, None]:
        """Server-Sent Events generator yielding progress events for a job."""
        job = self._jobs.get(job_id)
        if not job:
            yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
            return

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        self._subscribers[job_id].append(queue)

        # Send initial state
        initial_data = {
            "jobId": job.id,
            "status": job.status.value,
            "stage": job.current_stage,
            "progress": job.progress_percent,
        }
        yield f"event: progress\ndata: {json.dumps(initial_data)}\n\n"

        try:
            while True:
                data = await queue.get()
                event_name = "completed" if data.get("status") == "completed" else "progress"
                if data.get("status") == "failed":
                    event_name = "error"
                yield f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
                if data.get("status") in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.EXPIRED):
                    break
        finally:
            if job_id in self._subscribers and queue in self._subscribers[job_id]:
                self._subscribers[job_id].remove(queue)

    async def _broadcast_event(self, job_id: str, data: dict[str, Any]) -> None:
        if job_id in self._subscribers:
            for q in self._subscribers[job_id]:
                await q.put(data)

    async def execute_view_job(self, job_id: str) -> MetadataReport:
        """Extract metadata and build inspection report."""
        job = self._jobs.get(job_id)
        if not job or not job.file_info:
            raise ValueError("Invalid job")

        job.action = JobAction.VIEW
        await self.update_stage(job_id, JobStatus.ANALYZING, "analyzing", 30)

        job_dir = self.storage.get_job_dir(job_id)
        input_file = job_dir / f"in.{job.file_info.detected_type}"

        # Extract metadata
        raw_meta = extract_unified_metadata(input_file)
        report = build_metadata_report(job_id, job.file_info, raw_meta)

        self._reports[job_id] = report
        await self.update_stage(job_id, JobStatus.COMPLETED, "completed", 100)
        return report

    async def execute_remove_job(self, job_id: str, options: RemovalOptions | None = None) -> RemovalReport:
        """Execute lossless metadata removal with full before/after verification."""
        job = self._jobs.get(job_id)
        if not job or not job.file_info:
            raise ValueError("Invalid job")

        opts = options or RemovalOptions()
        job.action = JobAction.REMOVE
        job.options = opts

        # Stage 1: Analyzing & Strategy Selection
        await self.update_stage(job_id, JobStatus.ANALYZING, "analyzing", 20)
        job_dir = self.storage.get_job_dir(job_id)
        input_file = job_dir / f"in.{job.file_info.detected_type}"
        output_file = job_dir / f"out.{job.file_info.detected_type}"

        try:
            method, method_reason = select_cleaning_strategy(job.file_info.detected_type, opts)
        except StrategySelectionError as e:
            job.status = JobStatus.FAILED
            job.error = ErrorDetail(
                code=ErrorCode.REENCODE_REQUIRED if e.requires_reencode else ErrorCode.UNSUPPORTED_TYPE,
                message=str(e),
                hint="Enable re-encoding confirmation in removal options to proceed.",
            )
            await self._broadcast_event(job_id, {"jobId": job_id, "status": "failed", "error": job.error.model_dump()})
            raise

        before_meta = extract_unified_metadata(input_file)
        orig_stream_md5 = None
        if job.file_info.detected_type in ("mp4", "mov", "m4v", "mkv", "webm", "avi"):
            orig_stream_md5 = compute_stream_md5(input_file, "v")

        # Stage 2: Cleaning
        await self.update_stage(job_id, JobStatus.CLEANING, "cleaning", 50)
        norm_type = job.file_info.detected_type.lower()
        success = False
        error_msg = ""

        if norm_type in ("mp4", "mov", "m4v", "mkv", "webm", "avi"):
            success, error_msg = clean_video_lossless(input_file, output_file, norm_type, opts)
        elif norm_type in ("jpeg", "jpg", "png", "webp", "heic", "heif", "tiff"):
            success, error_msg = clean_image(input_file, output_file, norm_type, opts)
        else:
            success, error_msg = False, f"Unsupported format '{norm_type}' in Phase 1"

        if not success:
            job.status = JobStatus.FAILED
            job.error = ErrorDetail(
                code=ErrorCode.VERIFY_FAILED,
                message=error_msg,
                hint="The cleaning tool was unable to process this container.",
            )
            await self._broadcast_event(job_id, {"jobId": job_id, "status": "failed", "error": job.error.model_dump()})
            raise RuntimeError(error_msg)

        # Stage 3: Verifying
        await self.update_stage(job_id, JobStatus.VERIFYING, "verifying", 80)
        after_meta = extract_unified_metadata(output_file)

        stream_copy_verified = True
        clean_stream_md5 = None
        playback_ok = True

        if norm_type in ("mp4", "mov", "m4v", "mkv", "webm", "avi"):
            clean_stream_md5 = compute_stream_md5(output_file, "v")
            if orig_stream_md5 and clean_stream_md5:
                stream_copy_verified = (orig_stream_md5 == clean_stream_md5)
            playback_ok = verify_playback(output_file)

        # Compute cleaned SHA-256
        import hashlib
        hasher = hashlib.sha256()
        with open(output_file, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        cleaned_sha256 = hasher.hexdigest()

        # Build Removal Report
        report = build_removal_report(
            job_id=job_id,
            method=method,
            method_reason=method_reason,
            before_meta=before_meta,
            after_meta=after_meta,
            before_size=job.file_info.size_bytes,
            after_size=output_file.stat().st_size,
            original_sha256=job.file_info.sha256,
            cleaned_sha256=cleaned_sha256,
            stream_copy_verified=stream_copy_verified,
            playback_verified=playback_ok,
            orig_stream_md5=orig_stream_md5,
            clean_stream_md5=clean_stream_md5,
        )

        self._reports[job_id] = report

        # Sign download URL
        sig, exp = sign_download_url(job_id)
        job.download_url = f"/api/v1/jobs/{job_id}/download?signature={sig}&expires={exp}"

        await self.update_stage(job_id, JobStatus.COMPLETED, "completed", 100)
        return report

    def delete_job(self, job_id: str) -> bool:
        """Immediately delete job state and disk files."""
        self._jobs.pop(job_id, None)
        self._reports.pop(job_id, None)
        self._subscribers.pop(job_id, None)
        return self.storage.delete_job(job_id)


# Global singleton instance for the API process
job_service = JobService()
