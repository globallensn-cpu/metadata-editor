"""Reaboard Security Utilities.

Handles HMAC-SHA256 URL signing bound to job ID and output filename,
strict secret validation, RFC 6266 filename sanitization, and Content-Disposition headers.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from urllib.parse import quote

logger = logging.getLogger("reaboard.security")

DOWNLOAD_EXPIRATION_SECONDS = 900  # 15 minutes


def _initialize_secret_key() -> str:
    """Retrieve and validate HMAC signing key from environment.

    Enforces minimum 32-byte length in production. Generates an ephemeral
    random key with a warning in development mode. Refuses to start otherwise.
    """
    key = os.environ.get("REABOARD_SECRET_KEY", "").strip()
    env = os.environ.get("REABOARD_ENV", "prod").lower()

    if len(key) >= 32:
        return key

    if env in ("dev", "development", "test"):
        generated = secrets.token_hex(32)
        logger.warning(
            "REABOARD_SECRET_KEY is unset or <32 bytes. Generated ephemeral key for %s mode.",
            env,
        )
        return generated

    raise RuntimeError(
        "REABOARD_SECRET_KEY must be configured with at least 32 bytes in production environments."
    )


_SECRET_KEY: str = _initialize_secret_key()


def get_secret_key() -> str:
    """Return the active HMAC secret key."""
    return _SECRET_KEY


def sign_download_url(
    job_id: str,
    filename: str = "",
    expires_at: int | None = None,
) -> tuple[str, int]:
    """Generate an HMAC-SHA256 signature binding the job ID, filename, and expiration.

    Returns:
        (signature_hex, expires_at_timestamp)
    """
    if expires_at is None:
        expires_at = int(time.time()) + DOWNLOAD_EXPIRATION_SECONDS

    message = f"{job_id}:{expires_at}:{filename}".encode("utf-8")
    secret = get_secret_key().encode("utf-8")
    signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return signature, expires_at


def verify_download_signature(
    job_id: str,
    signature: str,
    expires_at: int,
    filename: str = "",
) -> bool:
    """Verify HMAC signature and check that the link has not expired."""
    current_time = int(time.time())
    if current_time > expires_at:
        return False

    expected_sig, _ = sign_download_url(job_id, filename, expires_at)
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

    if not clean or clean == ".":
        return fallback

    return clean[:200]


def format_content_disposition(filename: str) -> str:
    """Format RFC 6266 Content-Disposition header with safe ASCII fallback and UTF-8 encoding."""
    safe_ascii = sanitize_filename(filename, fallback="cleaned_file")
    encoded_utf8 = quote(filename, encoding="utf-8")
    return f'attachment; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded_utf8}'
