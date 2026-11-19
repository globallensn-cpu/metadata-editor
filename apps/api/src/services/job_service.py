"""Reaboard Job Service and State Manager.

Orchestrates job lifecycle transitions, event streaming (SSE),
and metadata inspection / removal execution across Redis and ARQ.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from apps.api.src.core.config import settings
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
    SurvivorClass,
)
from apps.worker.src.engine.cmd_runner import run_command_secure
from apps.worker.src.engine.pipelines.audio import clean_audio
from apps.worker.src.engine.pipelines.image import clean_image, get_exiftool_cmd
from apps.worker.src.engine.pipelines.office import clean_office
from apps.worker.src.engine.pipelines.pdf import clean_pdf
from apps.worker.src.engine.pipelines.video import clean_video_lossless, clean_video_reencode
from apps.worker.src.engine.strategy import StrategySelectionError, select_cleaning_strategy
from apps.worker.src.engine.verify import (
    build_metadata_report,
    build_removal_report,
    compute_all_stream_md5s,
    extract_media_duration,
    extract_unified_metadata,
    verify_playback,
)

logger = logging.getLogger("reaboard.job_service")

# Default job retention: 60 minutes
DEFAULT_JOB_RETENTION_MINUTES = 60

# Strict State Machine Valid Transitions
VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.CREATED: {JobStatus.UPLOADED, JobStatus.FAILED},
    JobStatus.UPLOADED: {JobStatus.QUEUED, JobStatus.FAILED, JobStatus.EXPIRED},
    JobStatus.QUEUED: {JobStatus.ANALYZING, JobStatus.FAILED, JobStatus.EXPIRED},
    JobStatus.ANALYZING: {
        JobStatus.CLEANING,
        JobStatus.COMPLETED,
        JobStatus.COMPLETED_WITH_WARNINGS,
        JobStatus.FAILED,
        JobStatus.EXPIRED,
    },
    JobStatus.CLEANING: {JobStatus.VERIFYING, JobStatus.FAILED, JobStatus.EXPIRED},
    JobStatus.VERIFYING: {
        JobStatus.COMPLETED,
        JobStatus.COMPLETED_WITH_WARNINGS,
        JobStatus.CLEANING,  # Allowed for pass 2
        JobStatus.FAILED,
        JobStatus.EXPIRED,
    },
    JobStatus.COMPLETED: set(),
    JobStatus.COMPLETED_WITH_WARNINGS: set(),
    JobStatus.FAILED: set(),
    JobStatus.EXPIRED: set(),
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal state machine transition is attempted."""

    def __init__(self, current_status: JobStatus, target_status: JobStatus) -> None:
        super().__init__(f"Cannot transition job from '{current_status.value}' to '{target_status.value}'")
        self.current_status = current_status
        self.target_status = target_status


class JobService:
    """Manages job records, state machine transitions, and execution."""

    def __init__(self, storage: StorageBackend | None = None) -> None:
        self.storage = storage or LocalStorageBackend(settings.storage_dir or None)
        self._jobs: dict[str, Job] = {}
        self._reports: dict[str, MetadataReport | RemovalReport] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._redis_client: Any = None
        self._arq_pool: Any = None
        self._redis_init_attempted: bool = False

    async def _get_redis(self) -> Any:
        """Lazily initialize Redis connection if configured."""
        if not self._redis_init_attempted:
            self._redis_init_attempted = True
            if settings.redis_url:
                try:
                    import redis.asyncio as aioredis
                    client = aioredis.from_url(settings.redis_url, decode_responses=True)
                    await client.ping()
                    self._redis_client = client
                    logger.info("Connected to Redis backend at %s", settings.redis_url)
                except Exception as e:
                    logger.warning("Redis connection failed, falling back to memory: %s", e)
                    self._redis_client = None

        return self._redis_client

    async def _get_arq_pool(self) -> Any:
        """Lazily initialize ARQ Redis pool if configured."""
        if self._arq_pool is None and settings.redis_url:
            try:
                import arq
                from arq.connections import RedisSettings
                pool = await arq.create_pool(RedisSettings.from_dsn(settings.redis_url))
                self._arq_pool = pool
                logger.info("Initialized ARQ pool for background worker dispatch")
            except Exception as e:
                logger.warning("ARQ pool initialization failed: %s", e)
                self._arq_pool = None
        return self._arq_pool

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def get_job_async(self, job_id: str) -> Job | None:
        """Fetch job from Redis hash or memory fallback."""
        r = await self._get_redis()
        if r:
            try:
                raw = await r.hget(f"job:{job_id}", "data")
                if raw:
                    job = Job.model_validate_json(raw)
                    self._jobs[job_id] = job
                    return job
            except Exception as e:
                logger.warning("Redis read error for job %s: %s", job_id, e)

        return self._jobs.get(job_id)

    def get_report(self, job_id: str) -> MetadataReport | RemovalReport | None:
        return self._reports.get(job_id)

    async def get_report_async(self, job_id: str) -> MetadataReport | RemovalReport | None:
        """Fetch report from Redis or memory fallback."""
        r = await self._get_redis()
        if r:
            try:
                raw = await r.get(f"report:{job_id}")
                if raw:
                    data = json.loads(raw)
                    # Determine report type
                    if "removed" in data:
                        rep = RemovalReport.model_validate(data)
                    else:
                        rep = MetadataReport.model_validate(data)
                    self._reports[job_id] = rep
                    return rep
            except Exception as e:
                logger.warning("Redis report read error for %s: %s", job_id, e)

        return self._reports.get(job_id)

    def create_job(
        self,
        original_filename: str,
        detected_mime: str,
        detected_type: str,
        size_bytes: int,
        sha256: str,
        job_id: str | None = None,
        batch_id: str | None = None,
    ) -> Job:
        """Create a new staged job record in 'uploaded' state."""
        jid = job_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=settings.retention_minutes)

        file_info = FileInfo(
            original_filename=original_filename,
            detected_mime=detected_mime,
            detected_type=detected_type,
            size_bytes=size_bytes,
            sha256=sha256,
        )

        job = Job(
            id=jid,
            batch_id=batch_id,
            status=JobStatus.UPLOADED,
            file_info=file_info,
            progress_percent=0,
            current_stage="uploaded",
            created_at=now,
            expires_at=expires_at,
        )
        self._jobs[jid] = job
        return job

    async def update_stage(
        self,
        job_id: str,
        target_status: JobStatus,
        stage_name: str,
        progress: int,
        error_detail: ErrorDetail | None = None,
        download_url: str | None = None,
    ) -> None:
        """Update job stage with strict state transition validation and broadcast to SSE/PubSub."""
        job = await self.get_job_async(job_id) or self._jobs.get(job_id)
        if not job:
            return

        # Validate transition
        allowed = VALID_TRANSITIONS.get(job.status, set())
        if target_status != job.status and target_status not in allowed:
            raise InvalidStateTransitionError(job.status, target_status)

        job.status = target_status
        job.current_stage = stage_name
        job.progress_percent = progress
        if error_detail:
            job.error = error_detail
        if download_url:
            job.download_url = download_url

        self._jobs[job_id] = job

        # Save to Redis if available
        r = await self._get_redis()
        if r:
            try:
                ttl = settings.retention_minutes * 60
                await r.hset(
                    f"job:{job_id}",
                    mapping={
                        "status": job.status.value,
                        "stage": stage_name,
                        "progress": str(progress),
                        "data": job.model_dump_json(by_alias=False),
                    },
                )
                await r.expire(f"job:{job_id}", ttl)
            except Exception as e:
                logger.warning("Failed to persist job %s to Redis: %s", job_id, e)

        # Broadcast event
        event_payload: dict[str, Any] = {
            "jobId": job_id,
            "status": target_status.value,
            "stage": stage_name,
            "progress": progress,
        }
        if error_detail:
            event_payload["error"] = error_detail.model_dump(by_alias=True)

        await self._broadcast_event(job_id, event_payload)

    async def _broadcast_event(self, job_id: str, data: dict[str, Any]) -> None:
        """Broadcast event to in-memory queues and Redis pub/sub channel."""
        # 1. Local in-memory subscribers
        if job_id in self._subscribers:
            for q in list(self._subscribers[job_id]):
                await q.put(data)

        # 2. Redis pub/sub
        r = await self._get_redis()
        if r:
            try:
                channel = f"job:{job_id}:events"
                await r.publish(channel, json.dumps(data))
            except Exception as e:
                logger.warning("Redis publish failed for %s: %s", job_id, e)

    async def subscribe_events(self, job_id: str) -> AsyncGenerator[str, None]:
        """Server-Sent Events generator yielding progress events for a job."""
        job = await self.get_job_async(job_id) or self.get_job(job_id)
        if not job:
            yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
            return

        # If job is already finished, immediately emit final event and exit
        if job.status in (JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_WARNINGS, JobStatus.FAILED, JobStatus.EXPIRED):
            event_name = "completed" if "completed" in job.status.value else "error"
            final_data = {
                "jobId": job.id,
                "status": job.status.value,
                "stage": job.current_stage,
                "progress": job.progress_percent,
            }
            if job.error:
                final_data["error"] = job.error.model_dump(by_alias=True)
            yield f"event: {event_name}\ndata: {json.dumps(final_data)}\n\n"
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

        # Subscribe to Redis pubsub if available
        r = await self._get_redis()
        pubsub = None
        pubsub_task = None
        if r:
            try:
                pubsub = r.pubsub()
                await pubsub.subscribe(f"job:{job_id}:events")

                async def _redis_listener() -> None:
                    try:
                        async for message in pubsub.listen():
                            if message["type"] == "message":
                                msg_data = json.loads(message["data"])
                                await queue.put(msg_data)
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.warning("Redis pubsub listener exception: %s", e)

                pubsub_task = asyncio.create_task(_redis_listener())
            except Exception as e:
                logger.warning("Could not subscribe to Redis pubsub: %s", e)

        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event_name = "completed" if "completed" in data.get("status", "") else "progress"
                    if data.get("status") in ("failed", "expired"):
                        event_name = "error"
                    yield f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
                    if data.get("status") in (
                        JobStatus.COMPLETED.value,
                        JobStatus.COMPLETED_WITH_WARNINGS.value,
                        JobStatus.FAILED.value,
                        JobStatus.EXPIRED.value,
                    ):
                        break
                except asyncio.TimeoutError:
                    # 15-second heartbeat comment
                    yield ": heartbeat\n\n"
        finally:
            if job_id in self._subscribers and queue in self._subscribers[job_id]:
                self._subscribers[job_id].remove(queue)
            if pubsub_task:
                pubsub_task.cancel()
            if pubsub and r:
                try:
                    await pubsub.unsubscribe(f"job:{job_id}:events")
                    await pubsub.close()
                except Exception:
                    pass

    async def enqueue_view_job(self, job_id: str) -> None:
        """Enqueue or run View job asynchronously."""
        pool = await self._get_arq_pool()
        if pool:
            await pool.enqueue_job("process_view_job", job_id)
        else:
            asyncio.create_task(self.execute_view_job(job_id))

    async def enqueue_remove_job(self, job_id: str, options: RemovalOptions | None = None) -> None:
        """Enqueue or run Remove job asynchronously."""
        pool = await self._get_arq_pool()
        opts_dict = options.model_dump() if options else {}
        if pool:
            await pool.enqueue_job("process_remove_job", job_id, opts_dict)
        else:
            asyncio.create_task(self.execute_remove_job(job_id, options))

    async def execute_view_job(self, job_id: str) -> MetadataReport:
        """Extract metadata and build inspection report."""
        job = await self.get_job_async(job_id) or self._jobs.get(job_id)
        if not job or not job.file_info:
            raise ValueError(f"Job not found or invalid: {job_id}")

        job.action = JobAction.VIEW
        await self.update_stage(job_id, JobStatus.ANALYZING, "analyzing", 30)

        job_dir = self.storage.get_job_dir(job_id)
        input_file = job_dir / f"in.{job.file_info.detected_type}"

        raw_meta = extract_unified_metadata(input_file)
        report = build_metadata_report(job_id, job.file_info, raw_meta)

        self._reports[job_id] = report

        # Persist report to Redis if available
        r = await self._get_redis()
        if r:
            try:
                ttl = settings.retention_minutes * 60
                await r.set(f"report:{job_id}", report.model_dump_json(by_alias=False), ex=ttl)
            except Exception as e:
                logger.warning("Failed to store report %s in Redis: %s", job_id, e)

        await self.update_stage(job_id, JobStatus.COMPLETED, "completed", 100)
        return report

    async def execute_remove_job(self, job_id: str, options: RemovalOptions | None = None) -> RemovalReport:
        """Execute lossless metadata removal with dual-pass verification and honest reporting."""
        job = await self.get_job_async(job_id) or self._jobs.get(job_id)
        if not job or not job.file_info:
            raise ValueError(f"Job not found or invalid: {job_id}")

        opts = options or RemovalOptions()
        job.action = JobAction.REMOVE
        job.options = opts

        # Stage 1: Analyzing & Strategy Selection
        await self.update_stage(job_id, JobStatus.ANALYZING, "analyzing", 20)
        job_dir = self.storage.get_job_dir(job_id)
        norm_type = job.file_info.detected_type.lower()
        input_file = job_dir / f"in.{norm_type}"
        output_file = job_dir / f"out.{norm_type}"

        try:
            method, method_reason = select_cleaning_strategy(norm_type, opts)
        except StrategySelectionError as e:
            err = ErrorDetail(
                code=ErrorCode.REENCODE_REQUIRED if e.requires_reencode else ErrorCode.UNSUPPORTED_TYPE,
                message=str(e),
                hint="Enable re-encoding confirmation in removal options to proceed."
                if e.requires_reencode
                else "Format is not supported for lossless metadata removal.",
            )
            await self.update_stage(job_id, JobStatus.FAILED, "failed", 0, error_detail=err)
            raise

        before_meta = extract_unified_metadata(input_file)
        stream_hashes_before: dict[str, str] = {}
        orig_duration: float | None = None

        if norm_type in ("mp4", "mov", "m4v", "mkv", "webm", "avi", "mp3", "m4a", "flac", "wav", "ogg"):
            stream_hashes_before = compute_all_stream_md5s(input_file)
            orig_duration = extract_media_duration(input_file)

        # Stage 2: Cleaning Pass 1
        await self.update_stage(job_id, JobStatus.CLEANING, "cleaning", 50)
        success = False
        error_msg = ""

        if norm_type in ("mp4", "mov", "m4v", "mkv", "webm", "avi"):
            success, error_msg = clean_video_lossless(input_file, output_file, norm_type, opts)
            if not success and opts.allow_reencode:
                logger.info("Lossless remux failed; falling back to authorized CRF 18 re-encode for %s", job_id)
                success, error_msg = clean_video_reencode(input_file, output_file, norm_type, opts)
                if success:
                    method = CleaningMethod.REENCODE_FALLBACK
                    method_reason = "Lossless remux was rejected; re-encoded with CRF 18 per explicit authorization."
        elif norm_type in ("jpeg", "jpg", "png", "webp", "heic", "heif", "tiff"):
            success, error_msg = clean_image(input_file, output_file, norm_type, opts)
        elif norm_type in ("mp3", "m4a", "flac", "wav", "ogg"):
            success, error_msg = clean_audio(input_file, output_file, norm_type, opts)
        elif norm_type == "pdf":
            success, error_msg = clean_pdf(input_file, output_file, opts)
        elif norm_type in ("docx", "xlsx", "pptx"):
            success, error_msg = clean_office(input_file, output_file, norm_type, opts)
        else:
            success, error_msg = False, f"Unsupported format '{norm_type}'"

        if not success:
            err = ErrorDetail(
                code=ErrorCode.VERIFY_FAILED,
                message=error_msg or "Failed to sanitize container metadata",
                hint="The cleaning engine encountered an unrecoverable container error.",
            )
            await self.update_stage(job_id, JobStatus.FAILED, "failed", 0, error_detail=err)
            raise RuntimeError(error_msg)

        # Stage 3: Verifying Pass 1
        await self.update_stage(job_id, JobStatus.VERIFYING, "verifying", 75)
        after_meta = extract_unified_metadata(output_file)

        stream_hashes_after: dict[str, str] = {}
        stream_copy_verified: bool | None = None
        playback_ok = True

        if norm_type in ("mp4", "mov", "m4v", "mkv", "webm", "avi", "mp3", "m4a", "flac", "wav", "ogg"):
            stream_hashes_after = compute_all_stream_md5s(output_file)
            playback_ok = verify_playback(output_file, orig_duration)
            if method == CleaningMethod.REMUX:
                stream_copy_verified = (
                    stream_hashes_before == stream_hashes_after and len(stream_hashes_before) > 0
                )
            else:
                stream_copy_verified = False
        else:
            # Images and Documents: Stream copy concept does not apply (honest reporting)
            stream_copy_verified = None

        hasher = hashlib.sha256()
        with open(output_file, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        cleaned_sha256 = hasher.hexdigest()

        # Build initial removal report
        report = build_removal_report(
            job_id=job_id,
            method=method,
            method_reason=method_reason,
            pass_number=1,
            before_meta=before_meta,
            after_meta=after_meta,
            before_size=job.file_info.size_bytes,
            after_size=output_file.stat().st_size,
            original_sha256=job.file_info.sha256,
            cleaned_sha256=cleaned_sha256,
            stream_copy_verified=stream_copy_verified,
            playback_verified=playback_ok,
            stream_hashes_before=stream_hashes_before,
            stream_hashes_after=stream_hashes_after,
        )

        # Check for identifying survivors
        identifying_count = sum(1 for s in report.survivors if s.survivor_class == SurvivorClass.IDENTIFYING)

        # Stage 4: Secondary Pass if identifying survivors persist
        if identifying_count > 0:
            logger.info("Job %s has %d identifying survivors after pass 1: executing pass 2 secondary strip", job_id, identifying_count)
            pass2_output = job_dir / f"out_pass2.{norm_type}"

            pass2_success = False
            if norm_type in ("mp4", "mov", "m4v", "mkv", "webm", "avi", "mp3", "m4a", "flac", "wav", "ogg"):
                # Secondary container strip via ExifTool
                exiftool_cmd = get_exiftool_cmd()
                cmd = exiftool_cmd + ["-all=", "-overwrite_original", "-o", str(pass2_output), str(output_file)]
                res = run_command_secure(cmd, timeout_seconds=45)
                pass2_success = (res.returncode == 0 and pass2_output.exists() and pass2_output.stat().st_size > 0)
            elif norm_type == "pdf":
                # Secondary QPDF pass
                qpdf = os.environ.get("REABOARD_QPDF_PATH", "qpdf")
                cmd = [qpdf, "--linearize", "--object-streams=generate", str(output_file), str(pass2_output)]
                res = run_command_secure(cmd, timeout_seconds=30)
                pass2_success = (res.returncode == 0 and pass2_output.exists() and pass2_output.stat().st_size > 0)
            elif norm_type in ("jpeg", "jpg", "png", "webp", "heic", "heif", "tiff"):
                exiftool_cmd = get_exiftool_cmd()
                cmd = exiftool_cmd + ["-all=", "-xmp:all=", "-exif:all=", "-iptc:all=", "-overwrite_original", "-o", str(pass2_output), str(output_file)]
                res = run_command_secure(cmd, timeout_seconds=45)
                pass2_success = (res.returncode == 0 and pass2_output.exists() and pass2_output.stat().st_size > 0)

            if pass2_success:
                shutil.move(str(pass2_output), str(output_file))
                after_meta = extract_unified_metadata(output_file)

                # Recompute cleaned SHA-256
                hasher2 = hashlib.sha256()
                with open(output_file, "rb") as f:
                    while chunk := f.read(65536):
                        hasher2.update(chunk)
                cleaned_sha256 = hasher2.hexdigest()

                report = build_removal_report(
                    job_id=job_id,
                    method=method,
                    method_reason=f"{method_reason} (Dual-pass secondary strip applied)",
                    pass_number=2,
                    before_meta=before_meta,
                    after_meta=after_meta,
                    before_size=job.file_info.size_bytes,
                    after_size=output_file.stat().st_size,
                    original_sha256=job.file_info.sha256,
                    cleaned_sha256=cleaned_sha256,
                    stream_copy_verified=stream_copy_verified,
                    playback_verified=playback_ok,
                    stream_hashes_before=stream_hashes_before,
                    stream_hashes_after=stream_hashes_after,
                )

        # Final survivor check
        final_identifying = sum(1 for s in report.survivors if s.survivor_class == SurvivorClass.IDENTIFYING)
        final_status = JobStatus.COMPLETED_WITH_WARNINGS if final_identifying > 0 else JobStatus.COMPLETED

        if final_status == JobStatus.COMPLETED_WITH_WARNINGS:
            report.warnings.append(
                f"{final_identifying} identifying metadata field(s) could not be safely removed without corrupting the file structure."
            )

        self._reports[job_id] = report

        # Store report in Redis if available
        r = await self._get_redis()
        if r:
            try:
                ttl = settings.retention_minutes * 60
                await r.set(f"report:{job_id}", report.model_dump_json(by_alias=False), ex=ttl)
            except Exception as e:
                logger.warning("Failed to store report %s in Redis: %s", job_id, e)

        # Sign download URL bound to filename and expiration
        orig_stem = Path(job.file_info.original_filename).stem
        dl_name = f"{orig_stem}_reaboard.{norm_type}"
        sig, exp = sign_download_url(job_id, filename=dl_name)
        download_url = f"/api/v1/jobs/{job_id}/download?signature={sig}&expires={exp}&dl_name={dl_name}"

        await self.update_stage(
            job_id,
            final_status,
            "completed",
            100,
            download_url=download_url,
        )
        return report

    def delete_job(self, job_id: str) -> bool:
        """Immediately delete job state and disk files."""
        self._jobs.pop(job_id, None)
        self._reports.pop(job_id, None)
        self._subscribers.pop(job_id, None)
        return self.storage.delete_job(job_id)


# Global singleton instance for the API process
job_service = JobService()
