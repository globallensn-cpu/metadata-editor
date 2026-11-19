"""Integration test for Video Remuxing Pipeline (Lossless Verification)."""

from pathlib import Path

from apps.api.src.schemas.schemas import RemovalOptions
from apps.worker.src.engine.pipelines.video import clean_video_lossless
from apps.worker.src.engine.verify import (
    compute_stream_md5,
    extract_unified_metadata,
    verify_playback,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
INPUT_MP4 = FIXTURE_DIR / "sample_gps.mp4"


def test_video_remux_lossless_integrity(tmp_path: Path):
    assert INPUT_MP4.exists(), "Synthetic test fixture must exist"

    output_mp4 = tmp_path / "cleaned_out.mp4"

    # 1. Compute original stream MD5
    orig_md5 = compute_stream_md5(INPUT_MP4, "v")
    assert orig_md5 is not None, "Original video stream MD5 should be computable"

    # 2. Extract original metadata to confirm GPS was present
    before_meta = extract_unified_metadata(INPUT_MP4)
    # Check that location or iPhone model was in before metadata
    all_before_tags = " ".join(f"{k}={v}" for k, v in before_meta.items())
    assert "iPhone 15 Pro" in all_before_tags or "37.7749" in all_before_tags

    # 3. Execute lossless remux
    success, msg = clean_video_lossless(
        input_path=INPUT_MP4,
        output_path=output_mp4,
        detected_type="mp4",
        options=RemovalOptions(),
    )
    assert success is True, f"Remux failed: {msg}"
    assert output_mp4.exists()
    assert output_mp4.stat().st_size > 0

    # 4. Verify stream packet MD5 equality (Lossless Guarantee)
    cleaned_md5 = compute_stream_md5(output_mp4, "v")
    assert cleaned_md5 == orig_md5, f"Stream MD5 altered! Orig: {orig_md5}, Clean: {cleaned_md5}"

    # 5. Playback decodability check
    playback_ok = verify_playback(output_mp4)
    assert playback_ok is True, "Output MP4 failed playback decodability verification"

    # 6. Extract cleaned metadata & verify GPS/device tags were stripped
    after_meta = extract_unified_metadata(output_mp4)
    all_after_tags = " ".join(f"{k}={v}" for k, v in after_meta.items())
    assert "37.7749" not in all_after_tags, "GPS latitude survived remux!"
    assert "iPhone 15 Pro" not in all_after_tags, "Device model tag survived remux!"
