"""Reaboard Worker Runner (ARQ / Redis).

Consumes jobs from Redis queue and executes the sandboxed pipeline.
"""

from __future__ import annotations

import logging
from typing import Any
from apps.api.src.schemas.schemas import RemovalOptions
from apps.api.src.services.job_service import job_service


logger = logging.getLogger("reaboard.worker")


async def process_view_job(ctx: dict[str, Any], job_id: str) -> dict[str, Any]:
    """Execute metadata extraction for view mode."""
    logger.info("Executing View job: %s", job_id)
    report = await job_service.execute_view_job(job_id)
    return report.model_dump()


async def process_remove_job(ctx: dict[str, Any], job_id: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute metadata removal and verification for remove mode."""
    logger.info("Executing Remove job: %s", job_id)
    opts = RemovalOptions(**(options or {}))
    report = await job_service.execute_remove_job(job_id, opts)
    return report.model_dump()


class WorkerSettings:
    functions = [process_view_job, process_remove_job]
    redis_settings = None  # Loaded from env in production container
    max_jobs = 1  # 1 job at a time per worker process for isolation
    job_timeout = 360
