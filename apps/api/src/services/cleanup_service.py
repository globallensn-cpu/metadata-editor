"""Reaboard Cleanup Scheduler.

Runs every 5 minutes to purge expired jobs (>60 min) and orphaned directories.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from apps.api.src.core.storage import StorageBackend
from apps.api.src.schemas.schemas import JobStatus
from apps.api.src.services.job_service import JobService


logger = logging.getLogger("reaboard.cleanup")


class CleanupService:
    def __init__(self, job_service: JobService, interval_seconds: int = 300) -> None:
        self.job_service = job_service
        self.interval = interval_seconds
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def sweep_once(self) -> int:
        """Purge jobs whose expiration timestamp has passed."""
        now = datetime.utcnow()
        expired_ids: list[str] = []

        for job_id, job in list(self.job_service._jobs.items()):
            if job.expires_at <= now:
                expired_ids.append(job_id)

        count = 0
        for job_id in expired_ids:
            logger.info("Purging expired job: %s", job_id)
            self.job_service.delete_job(job_id)
            count += 1

        return count

    async def _loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                purged = await self.sweep_once()
                if purged > 0:
                    logger.info("Cleanup cycle purged %d expired jobs.", purged)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error during cleanup sweep: %s", e)

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
