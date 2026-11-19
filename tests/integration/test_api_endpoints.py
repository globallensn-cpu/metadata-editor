"""Integration tests for FastAPI REST Endpoints."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from apps.api.src.core.security import sign_download_url
from apps.api.src.main import app
from apps.api.src.services.job_service import job_service


client = TestClient(app)
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_MP4 = FIXTURE_DIR / "sample_gps.mp4"
HOSTILE_MP4 = FIXTURE_DIR / "hostile_script.mp4"


def test_health_and_readiness():
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

    res = client.get("/readyz")
    assert res.status_code == 200
    assert res.json().get("status") == "ready"


def test_upload_rejects_hostile_type_mismatch():
    assert HOSTILE_MP4.exists()
    with open(HOSTILE_MP4, "rb") as f:
        res = client.post("/api/v1/jobs", files={"file": ("fake_video.mp4", f, "video/mp4")})
    # Magic bytes will detect text/script rather than MP4 ftyp atom
    assert res.status_code == 415
    data = res.json()
    assert "error" in data


def test_full_job_lifecycle_upload_remove_download_delete():
    assert SAMPLE_MP4.exists()

    # 1. Upload valid MP4
    with open(SAMPLE_MP4, "rb") as f:
        res = client.post("/api/v1/jobs", files={"file": ("iphone_video.mp4", f, "video/mp4")})
    assert res.status_code == 201
    upload_data = res.json()
    job_id = upload_data["jobId"]
    assert upload_data["detectedType"] == "mp4"

    # 2. Check Job status
    res = client.get(f"/api/v1/jobs/{job_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "uploaded"

    # 3. Trigger Remove Metadata
    res = client.post(f"/api/v1/jobs/{job_id}/remove", json={"keepIccProfile": True})
    assert res.status_code == 202

    # Wait briefly for synchronous test processing in job_service
    import time
    for _ in range(20):
        res = client.get(f"/api/v1/jobs/{job_id}")
        if res.json()["status"] == "completed":
            break
        time.sleep(0.2)

    job_data = res.json()
    assert job_data["status"] == "completed"
    dl_url = job_data.get("download_url") or job_data.get("downloadUrl")
    assert dl_url is not None

    # 4. Fetch Removal Report
    res = client.get(f"/api/v1/jobs/{job_id}/report")
    assert res.status_code == 200
    report = res.json()
    assert report.get("job_id") == job_id or report.get("jobId") == job_id
    assert report["method"] == "remux"
    assert report["stream_copy"] is True or report.get("streamCopy") is True
    assert report["playback_verified"] is True or report.get("playbackVerified") is True
    assert "removed" in report
    assert "counts" in report

    # 5. Download Cleaned File with Valid Signature
    sig, exp = sign_download_url(job_id)
    dl_res = client.get(f"/api/v1/jobs/{job_id}/download?signature={sig}&expires={exp}")
    assert dl_res.status_code == 200
    assert "attachment" in dl_res.headers.get("content-disposition", "")
    assert len(dl_res.content) > 0

    # 6. Reject Download with Forged Signature
    dl_forged = client.get(f"/api/v1/jobs/{job_id}/download?signature=fakehexsignature&expires={exp}")
    assert dl_forged.status_code == 401

    # 7. Delete Job Immediately
    del_res = client.delete(f"/api/v1/jobs/{job_id}")
    assert del_res.status_code == 204

    # Confirm purged
    get_purged = client.get(f"/api/v1/jobs/{job_id}")
    assert get_purged.status_code == 404
