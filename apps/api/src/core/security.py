"""Reaboard Security Utilities.

Handles HMAC-SHA256 signing for expiring download links, filename sanitization (RFC 6266),
and path traversal defenses.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from pathlib import Path


DEFAULT_SECRET = "reaboard-dev-secret-change-in-production-1984"
DOWNLOAD_EXPIRATION_SECONDS = 900  # 15 minutes


def get_secret_key() -> str:
    """Retrieve HMAC signing key from environment or fallback to default."""
    return os.environ.get("REABOARD_SECRET_KEY", DEFAULT_SECRET)


def sign_download_url(job_id: str, expires_at: int | None = None) -> tuple[str, int]:
    """Generate an HMAC-SHA256 signature for a specific job ID.

    Returns:
        (signature_hex, expires_at_timestamp)
    """
    if expires_at is None:
        expires_at = int(time.time()) + DOWNLOAD_EXPIRATION_SECONDS

    message = f"{job_id}:{expires_at}".encode("utf-8")
    secret = get_secret_key().encode("utf-8")
    signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return signature, expires_at


def verify_download_signature(job_id: str, signature: str, expires_at: int) -> bool:
    """Verify HMAC signature and check that the link has not expired."""
    current_time = int(time.time())
    if current_time > expires_at:
        return False

    expected_sig, _ = sign_download_url(job_id, expires_at)
    return hmac.compare_digest(expected_sig, signature)


def sanitize_filename(filename: str, fallback: str = "cleaned_file") -> str:
    """Sanitize user-provided filename to prevent path traversal and header injection (RFC 6266).

    Strips directory separators, shell metacharacters, control characters, and quotes.
    """
    if not filename:
        return fallback

    # Strip directory components to prevent path traversal
    clean = filename.replace("\\", "/").rstrip("/").split("/")[-1]

    # Remove non-whitelisted characters: allow alphanumeric, dots, underscores, dashes
    clean = re.sub(r"[^\w\.\-]", "_", clean)

    # Avoid leading dots (hidden files) or consecutive dots (directory traversal)
    clean = re.sub(r"^\.+", "", clean)
    clean = re.sub(r"\.{2,}", ".", clean)

    # If nothing valid survives, use fallback
    if not clean or clean == ".":
        return fallback

    # Cap length to 200 characters
    return clean[:200]
