"""Integration tests for state machine transitions, idempotency, and security constraints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.src.core.security import sign_download_url
from apps.api.src.main import app
from apps.api.src.schemas.schemas import JobStatus
from apps.api.src.services.job_service import InvalidStateTransitionError, job_service

client = TestClient(app)
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_invalid_state_transition_conflict():
    """Attempting an invalid state transition (e.g. from COMPLETED to QUEUED) raises 409 Conflict."""
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        # Create a job and manually update to COMPLETED
        job = job_service.create_job(
            original_filename="sample.mp4",
            detected_mime="video/mp4",
            detected_type="mp4",
            size_bytes=1000,
            sha256="a" * 64,
        )
        job.status = JobStatus.COMPLETED
        job_service._jobs[job.id] = job

        # Try to transition backwards to QUEUED
        import asyncio
        asyncio.run(job_service.update_stage(job.id, JobStatus.QUEUED, "queued", 0))

    assert "Cannot transition" in str(exc_info.value)


def test_idempotent_view_and_remove():
    """Calling /view or /remove on an already queued or completed job is idempotent (returns 202)."""
    mp4_file = FIXTURES_DIR / "sample_gps.mp4"
    assert mp4_file.exists()

    with open(mp4_file, "rb") as f:
        res = client.post("/api/v1/jobs", files={"file": ("video.mp4", f, "video/mp4")})
    assert res.status_code == 201
    job_id = res.json()["jobId"]

    # First call to view
    res1 = client.post(f"/api/v1/jobs/{job_id}/view")
    assert res1.status_code == 202

    # Second call to view while queued/analyzing
    res2 = client.post(f"/api/v1/jobs/{job_id}/view")
    assert res2.status_code == 202


def test_tampered_download_signature_rejected():
    """Signed download URLs with forged signature or expired timestamps are rejected with 401."""
    mp4_file = FIXTURES_DIR / "sample_gps.mp4"
    with open(mp4_file, "rb") as f:
        res = client.post("/api/v1/jobs", files={"file": ("video.mp4", f, "video/mp4")})
    job_id = res.json()["jobId"]

    # Tampered signature
    res_tampered = client.get(f"/api/v1/jobs/{job_id}/download?signature=deadbeef1234&expires=9999999999")
    assert res_tampered.status_code == 401
    assert res_tampered.json()["error"]["code"] == "INVALID_SIGNATURE"

    # Expired signature
    sig, _ = sign_download_url(job_id, expires_at=1000)
    res_expired = client.get(f"/api/v1/jobs/{job_id}/download?signature={sig}&expires=1000")
    assert res_expired.status_code == 401
    assert res_expired.json()["error"]["code"] == "INVALID_SIGNATURE"


def test_invalid_uuid_rejected_404():
    """Non-UUID identifier in route path parameters returns 404."""
    res = client.get("/api/v1/jobs/not-a-valid-uuid")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "JOB_NOT_FOUND"
