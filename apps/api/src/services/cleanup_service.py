"""Reaboard Cleanup Scheduler.

Runs periodically to purge expired jobs (>60 min default) and orphaned storage directories.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from apps.api.src.core.config import settings
from apps.api.src.services.job_service import JobService

logger = logging.getLogger("reaboard.cleanup")


class CleanupService:
    def __init__(self, job_service: JobService, interval_seconds: int = 300) -> None:
        self.job_service = job_service
        self.interval = interval_seconds
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def sweep_once(self) -> int:
        """Purge jobs whose expiration timestamp has passed and prune orphaned disk directories."""
        now = datetime.now(timezone.utc)
        expired_ids: list[str] = []

        # 1. Sweep expired memory/known jobs
        for job_id, job in list(self.job_service._jobs.items()):
            if job.expires_at <= now:
                expired_ids.append(job_id)

        count = 0
        for job_id in expired_ids:
            logger.info("Purging expired job: %s", job_id)
            self.job_service.delete_job(job_id)
            count += 1

        # 2. Sweep orphaned disk directories
        orphaned_count = self.sweep_orphaned_directories()
        return count + orphaned_count

    def sweep_orphaned_directories(self) -> int:
        """Purge disk directories older than retention period without active memory/Redis job."""
        base_dir: Path = self.job_service.storage.base_dir
        if not base_dir.exists():
            return 0

        cutoff = time.time() - (settings.retention_minutes * 60)
        orphans_purged = 0

        try:
            for item in base_dir.iterdir():
                if item.is_dir():
                    try:
                        mtime = item.stat().st_mtime
                        if mtime < cutoff:
                            # Verify if job is still active
                            if item.name not in self.job_service._jobs:
                                logger.info("Pruning orphaned storage directory: %s", item.name)
                                shutil.rmtree(item, ignore_errors=True)
                                orphans_purged += 1
                    except Exception as e:
                        logger.warning("Error inspecting storage folder %s: %s", item, e)
        except Exception as e:
            logger.warning("Error reading storage base dir %s: %s", base_dir, e)

        return orphans_purged

    async def _loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                purged = await self.sweep_once()
                if purged > 0:
                    logger.info("Cleanup cycle purged %d expired jobs/orphaned directories.", purged)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error during cleanup sweep: %s", e)

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())
            logger.info("Cleanup service scheduler started (interval=%ds)", self.interval)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            logger.info("Cleanup service scheduler stopped")
