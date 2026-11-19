"""Reaboard Storage Backend Protocol and Local Ephemeral Implementation.

Safely handles chunked file streaming, hash calculation, quota checks, and disk unlinking.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Generator
from pathlib import Path


DEFAULT_MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB


class StorageBackend(ABC):
    """Abstract storage interface for ephemeral files."""

    @abstractmethod
    def get_job_dir(self, job_id: str) -> Path:
        """Return the root path for a job's ephemeral files."""
        ...

    @abstractmethod
    def save_stream(
        self,
        job_id: str,
        filename: str,
        stream: Generator[bytes, None, None],
        max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ) -> tuple[Path, int, str]:
        """Save a synchronous chunk stream to disk.
        
        Returns:
            (file_path, total_bytes_written, sha256_hex)
        """
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
    """Local ephemeral directory storage (tmpfs or disk)."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        if base_dir is None:
            # Default to system temp /reaboard or environment override
            env_dir = os.environ.get("REABOARD_STORAGE_DIR")
            if env_dir:
                self.base_dir = Path(env_dir).resolve()
            else:
                self.base_dir = Path("/tmp/reaboard").resolve() if os.name != "nt" else Path("D:/code metadata/.reaboard_storage").resolve()
        else:
            self.base_dir = Path(base_dir).resolve()

        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _safe_resolve(self, job_id: str, filename: str | None = None) -> Path:
        """Resolve path ensuring it does not escape base_dir."""
        # Clean job_id (must be alphanumeric or dashes / UUID)
        clean_id = "".join(c for c in job_id if c.isalnum() or c == "-")
        if not clean_id:
            raise ValueError(f"Invalid job ID: {job_id}")

        job_dir = (self.base_dir / clean_id).resolve()
        if not str(job_dir).startswith(str(self.base_dir)):
            raise ValueError("Path traversal detected in job directory resolution")

        if filename:
            # Filename should be internal sanitized name like in.mp4, out.mp4
            clean_name = Path(filename).name
            target = (job_dir / clean_name).resolve()
            if not str(target).startswith(str(job_dir)):
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
        max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
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
                    # Clean up partial write before raising
                    f.close()
                    if target_path.exists():
                        target_path.unlink()
                    raise ValueError(f"File size exceeds maximum allowed limit of {max_bytes} bytes")
                sha256.update(chunk)
                f.write(chunk)

        return target_path, bytes_written, sha256.hexdigest()

    async def save_async_stream(
        self,
        job_id: str,
        filename: str,
        stream: AsyncIterator[bytes],
        max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
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
                    if target_path.exists():
                        target_path.unlink()
                    raise ValueError(f"File size exceeds maximum allowed limit of {max_bytes} bytes")
                sha256.update(chunk)
                f.write(chunk)

        return target_path, bytes_written, sha256.hexdigest()

    def delete_job(self, job_id: str) -> bool:
        job_dir = self._safe_resolve(job_id)
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
            return True
        return False

    def list_jobs(self) -> list[str]:
        if not self.base_dir.exists():
            return []
        return [p.name for p in self.base_dir.iterdir() if p.is_dir()]
