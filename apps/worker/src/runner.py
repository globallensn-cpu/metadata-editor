"""Reaboard Worker Runner (ARQ / Redis).

Consumes jobs from the Redis queue and executes the sandboxed pipeline in single-job isolation mode.
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any

from arq.connections import RedisSettings

from apps.api.src.schemas.schemas import RemovalOptions
from apps.api.src.services.job_service import job_service

logger = logging.getLogger("reaboard.worker")


async def startup(ctx: dict[str, Any]) -> None:
    """Worker startup hook."""
    logger.info("Reaboard worker process started (max_jobs=1, isolation mode)")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Worker shutdown hook."""
    logger.info("Reaboard worker process shutting down")


async def process_view_job(ctx: dict[str, Any], job_id: str) -> dict[str, Any]:
    """Execute metadata extraction for view mode."""
    logger.info("Worker picked up View job: %s", job_id)
    job_dir = job_service.storage.get_job_dir(job_id)
    scratch_dir = job_dir / "worker_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    try:
        report = await job_service.execute_view_job(job_id)
        return report.model_dump(by_alias=True)
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


async def process_remove_job(
    ctx: dict[str, Any],
    job_id: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute metadata removal and verification for remove mode."""
    logger.info("Worker picked up Remove job: %s", job_id)
    opts = RemovalOptions(**(options or {}))
    job_dir = job_service.storage.get_job_dir(job_id)
    scratch_dir = job_dir / "worker_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    try:
        report = await job_service.execute_remove_job(job_id, opts)
        return report.model_dump(by_alias=True)
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


class WorkerSettings:
    """ARQ Worker configuration for Reaboard media processing."""

    functions = [process_view_job, process_remove_job]
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://redis:6379/0")
    )
    max_jobs = 1  # 1 job at a time per worker container for strict resource isolation
    job_timeout = 360  # 6-minute hard timeout per job
    on_startup = startup
    on_shutdown = shutdown
