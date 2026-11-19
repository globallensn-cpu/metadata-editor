"""Reaboard Video Cleaning Pipeline.

Executes lossless remuxing for MP4, MOV, M4V, MKV, WebM, and AVI containers.
Strips telemetry, GPS data tracks, chapter markers, container metadata, and handler tags
while keeping video and audio bit-for-bit lossless via stream copy.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from apps.api.src.schemas.schemas import CleaningMethod, RemovalOptions


# Hard timeout: 300 seconds default
DEFAULT_COMMAND_TIMEOUT = 300


def get_ffmpeg_path() -> str:
    """Find ffmpeg binary from PATH or common locations."""
    return os.environ.get("REABOARD_FFMPEG_PATH", "ffmpeg")


def clean_video_lossless(
    input_path: Path,
    output_path: Path,
    detected_type: str,
    options: RemovalOptions | None = None,
    timeout: int = DEFAULT_COMMAND_TIMEOUT,
) -> tuple[bool, str]:
    """Execute lossless remuxing to strip metadata without re-encoding.

    Returns:
        (success: bool, error_message_or_info: str)
    """
    opts = options or RemovalOptions()
    ffmpeg = get_ffmpeg_path()
    norm_type = detected_type.lower()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i", str(input_path),
        "-map", "0",
        "-map", "-0:d?",           # Drop GPS / camera telemetry / telemetry data tracks
        "-map", "-0:t?",           # Drop font & file attachment streams
        "-map_metadata", "-1",     # Drop global container tags
        "-map_chapters", "-1",     # Strip chapter markers
        "-c", "copy",              # Pure stream copy - zero generational loss
        "-fflags", "+bitexact",    # Bitexact container mode (suppresses Lavf encoder tags)
        "-flags:v", "+bitexact",
        "-flags:a", "+bitexact",
    ]

    # QuickTime / MP4 family specifics
    if norm_type in ("mp4", "mov", "m4v"):
        cmd.extend([
            "-movflags", "+faststart",
            "-metadata:s:v", "handler_name=",
            "-metadata:s:a", "handler_name=",
            "-metadata:s:s", "handler_name=",
        ])

    # Pass separator before destination
    cmd.extend(["--", str(output_path)])

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            shell=False,
        )
        if proc.returncode != 0:
            err = proc.stderr.strip()[-500:] if proc.stderr else "Unknown FFmpeg error"
            return False, f"FFmpeg remux failed with code {proc.returncode}: {err}"

        if not output_path.exists() or output_path.stat().st_size == 0:
            return False, "FFmpeg completed but output file is missing or empty"

        return True, "Lossless remux completed successfully"

    except subprocess.TimeoutExpired:
        return False, f"Remux operation timed out after {timeout} seconds"
    except Exception as e:
        return False, f"Unexpected error executing FFmpeg: {str(e)}"
