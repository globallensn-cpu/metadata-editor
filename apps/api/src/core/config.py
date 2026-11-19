"""Reaboard Application Configuration.

Centralizes environment variables, upload limits, rate limiting thresholds,
retention policies, and CORS definitions.
"""

from __future__ import annotations

import os


def get_env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").strip().lower()
    if not val:
        return default
    return val in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        self.env: str = os.environ.get("REABOARD_ENV", "dev").lower()
        self.max_upload_mb: int = int(os.environ.get("REABOARD_MAX_UPLOAD_MB", "500"))
        self.max_upload_bytes: int = self.max_upload_mb * 1024 * 1024

        self.retention_minutes: int = int(os.environ.get("REABOARD_RETENTION_MINUTES", "60"))
        self.rate_limit_uploads_per_hour: int = int(
            os.environ.get("REABOARD_RATE_LIMIT_UPLOADS_PER_HOUR", "30")
        )

        self.redis_url: str = os.environ.get("REDIS_URL", "").strip()

        # CORS origins: comma-separated list
        cors_raw = os.environ.get("REABOARD_CORS_ORIGINS", "").strip()
        self.cors_origins: list[str] = [orig.strip() for orig in cors_raw.split(",") if orig.strip()]

        # Storage directory
        self.storage_dir: str = os.environ.get("REABOARD_STORAGE_DIR", "").strip()


settings = Settings()
