"""Script to generate synthetic test media fixtures with injected metadata."""

import subprocess
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)


def create_synthetic_mp4():
    """Create a 1-second MP4 with injected GPS and device tags via FFmpeg."""
    out_file = FIXTURE_DIR / "sample_gps.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=1:size=320x240:rate=15",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-metadata", "location=+37.7749-122.4194/",
        "-metadata", "location-eng=+37.7749-122.4194/",
        "-metadata", "model=iPhone 15 Pro",
        "-metadata", "make=Apple",
        "-metadata", "creation_time=2026-11-19T09:00:00.000000Z",
        "-metadata:s:v", "handler_name=Core Media Video",
        str(out_file),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("Created synthetic MP4:", out_file)


def create_hostile_file():
    """Create a text script disguised as MP4 to test magic byte rejection."""
    out_file = FIXTURE_DIR / "hostile_script.mp4"
    out_file.write_text("#!/bin/sh\necho 'exploit attempt'\n")
    print("Created hostile script test:", out_file)


def create_synthetic_jpg():
    """Create a 1-pixel or small test JPEG via FFmpeg."""
    out_file = FIXTURE_DIR / "sample_test.jpg"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "color=c=blue:s=160x120:d=1",
        "-vframes", "1",
        str(out_file),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("Created synthetic JPEG:", out_file)


if __name__ == "__main__":
    create_synthetic_mp4()
    create_hostile_file()
    create_synthetic_jpg()
