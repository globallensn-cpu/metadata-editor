"""Reaboard Storage Backend Protocol and Local Ephemeral Implementation.

Safely handles chunked file streaming, hash calculation, quota checks, and disk unlinking.
Strictly isolates job directories using Path.is_relative_to and UUID validation.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Generator
from pathlib import Path


def get_default_storage_dir() -> Path:
    """Determine root storage directory from environment or OS temporary directory."""
    env_dir = os.environ.get("REABOARD_STORAGE_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    return Path(tempfile.gettempdir()).resolve() / "reaboard"


class StorageBackend(ABC):
    """Abstract storage interface for ephemeral files."""

    @abstractmethod
    def get_job_dir(self, job_id: str) -> Path:
        """Return the root path for a job's ephemeral files."""
        ...

    @abstractmethod
    def delete_job(self, job_id: str) -> bool:
        """Immediately delete all files and directory for a job."""
        ...

    @abstractmethod
    def list_jobs(self) -> list[str]:
        """List all active job IDs present in storage."""
        ...


class LocalStorageBackend(StorageBackend):
    """Local ephemeral directory storage with strict path isolation."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        if base_dir is None:
            self.base_dir = get_default_storage_dir()
        else:
            self.base_dir = Path(base_dir).resolve()

        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _safe_resolve(self, job_id: str, filename: str | None = None) -> Path:
        """Resolve path ensuring job_id is valid UUID and target does not escape base_dir."""
        # Strictly validate UUID format
        try:
            val = uuid.UUID(str(job_id))
            clean_id = str(val)
        except (ValueError, AttributeError, TypeError):
            raise ValueError(f"Invalid job ID format: '{job_id}'. Must be a valid UUID.")

        job_dir = (self.base_dir / clean_id).resolve()
        if not job_dir.is_relative_to(self.base_dir):
            raise ValueError("Path traversal detected in job directory resolution")

        if filename:
            clean_name = Path(filename).name
            target = (job_dir / clean_name).resolve()
            if not target.is_relative_to(job_dir):
                raise ValueError("Path traversal detected in file resolution")
            return target

        return job_dir

    def get_job_dir(self, job_id: str) -> Path:
        job_dir = self._safe_resolve(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def save_stream(
        self,
        job_id: str,
        filename: str,
        stream: Generator[bytes, None, None],
        max_bytes: int = 500 * 1024 * 1024,
    ) -> tuple[Path, int, str]:
        job_dir = self.get_job_dir(job_id)
        target_path = self._safe_resolve(job_id, filename)

        sha256 = hashlib.sha256()
        bytes_written = 0

        with open(target_path, "wb") as f:
            for chunk in stream:
                if not chunk:
                    continue
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    f.close()
                    target_path.unlink(missing_ok=True)
                    shutil.rmtree(job_dir, ignore_errors=True)
                    raise ValueError(f"File size exceeds maximum allowed limit of {max_bytes} bytes")
                sha256.update(chunk)
                f.write(chunk)

        return target_path, bytes_written, sha256.hexdigest()

    async def save_async_stream(
        self,
        job_id: str,
        filename: str,
        stream: AsyncIterator[bytes],
        max_bytes: int = 500 * 1024 * 1024,
    ) -> tuple[Path, int, str]:
        """Asynchronous stream writer for FastAPI UploadFile."""
        job_dir = self.get_job_dir(job_id)
        target_path = self._safe_resolve(job_id, filename)

        sha256 = hashlib.sha256()
        bytes_written = 0

        with open(target_path, "wb") as f:
            async for chunk in stream:
                if not chunk:
                    continue
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    f.close()
                    target_path.unlink(missing_ok=True)
                    shutil.rmtree(job_dir, ignore_errors=True)
                    raise ValueError(f"File size exceeds maximum allowed limit of {max_bytes} bytes")
                sha256.update(chunk)
                f.write(chunk)

        return target_path, bytes_written, sha256.hexdigest()

    def delete_job(self, job_id: str) -> bool:
        try:
            job_dir = self._safe_resolve(job_id)
        except ValueError:
            return False

        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
            return True
        return False

    def list_jobs(self) -> list[str]:
        if not self.base_dir.exists():
            return []
        return [p.name for p in self.base_dir.iterdir() if p.is_dir()]
