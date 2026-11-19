"""Reaboard Audio Sanitization Pipeline.

Strips ID3v1, ID3v2, APEv2, Vorbis comments, LIST INFO chunks, and embedded cover art
for MP3, M4A, FLAC, WAV, and OGG containers using lossless bitexact stream copying.
"""

from __future__ import annotations

from pathlib import Path

from apps.api.src.schemas.schemas import RemovalOptions
from apps.worker.src.engine.cmd_runner import run_command_secure
from apps.worker.src.engine.pipelines.image import get_exiftool_cmd
from apps.worker.src.engine.pipelines.video import get_ffmpeg_path

DEFAULT_COMMAND_TIMEOUT = 180


def clean_audio(
    input_path: Path,
    output_path: Path,
    detected_type: str,
    options: RemovalOptions | None = None,
    timeout: int = DEFAULT_COMMAND_TIMEOUT,
) -> tuple[bool, str]:
    """Clean audio containers using lossless stream copy and ExifTool tag stripping."""
    ffmpeg = get_ffmpeg_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    detected_type.lower()

    # Step 1: Lossless stream copy without metadata or attached picture streams
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i", str(input_path),
        "-map", "0:a",            # Select audio stream only (drops video/album art streams)
        "-map_metadata", "-1",     # Strip container metadata
        "-c", "copy",              # Lossless stream copy
        "-fflags", "+bitexact",
        "-flags:a", "+bitexact",
    ]

    cmd.extend(["--", str(output_path)])

    res = run_command_secure(cmd, timeout_seconds=timeout)
    if res.timed_out:
        return False, f"Audio remux timed out after {timeout} seconds"

    if res.returncode != 0:
        err = res.stderr.strip()[-500:] if res.stderr else "Audio remux failed"
        return False, f"FFmpeg audio remux failed: {err}"

    # Step 2: ExifTool pass to clear any lingering ID3/INFO headers on output
    exiftool = get_exiftool_cmd()
    cmd_exif = list(exiftool) + [
        "-all=",
        "-overwrite_original",
        "-P",
        "--",
        str(output_path),
    ]
    run_command_secure(cmd_exif, timeout_seconds=timeout)

    if not output_path.exists() or output_path.stat().st_size == 0:
        return False, "Cleaned audio file is missing or zero-byte"

    return True, "Audio container metadata and album art stripped successfully"
