"""Unit tests for Security Utilities (HMAC URLs, Filename Sanitization)."""

import time

from apps.api.src.core.security import (
    sanitize_filename,
    sign_download_url,
    verify_download_signature,
)


def test_sign_and_verify_download_url():
    job_id = "test-job-uuid-1234"
    signature, expires_at = sign_download_url(job_id)

    # Valid signature
    assert verify_download_signature(job_id, signature, expires_at) is True

    # Tampered job ID
    assert verify_download_signature("another-job-id", signature, expires_at) is False

    # Tampered signature
    assert verify_download_signature(job_id, signature + "evil", expires_at) is False

    # Expired timestamp
    past_timestamp = int(time.time()) - 100
    expired_sig, _ = sign_download_url(job_id, past_timestamp)
    assert verify_download_signature(job_id, expired_sig, past_timestamp) is False


def test_sanitize_filename_traversal():
    assert sanitize_filename("../../../etc/passwd.mp4") == "passwd.mp4"
    assert sanitize_filename("..\\..\\windows\\system32.dll") == "system32.dll"
    assert sanitize_filename("normal_video.mp4") == "normal_video.mp4"


def test_sanitize_filename_shell_characters():
    assert sanitize_filename('test;rm -rf;$(calc).mp4') == "test_rm_-rf___calc_.mp4"
    assert sanitize_filename('video "quotes".mov') == "video__quotes_.mov"


def test_sanitize_filename_empty_fallback():
    assert sanitize_filename("") == "cleaned_file"
    assert sanitize_filename("....") == "cleaned_file"
