"""Reaboard Video Cleaning Pipeline.

Executes lossless remuxing for MP4, MOV, M4V, MKV, WebM, and AVI containers.
Normalizes handler names to generic structural names, drops data and telemetry streams,
and provides CRF-based re-encoding when lossless processing fails and user explicitly permits it.
"""

from __future__ import annotations

import os
from pathlib import Path

from apps.api.src.schemas.schemas import RemovalOptions
from apps.worker.src.engine.cmd_runner import run_command_secure

DEFAULT_COMMAND_TIMEOUT = 300


def get_ffmpeg_path() -> str:
    """Find ffmpeg binary from environment or system path."""
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
    options or RemovalOptions()
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
            # Note: FFmpeg normalizes empty handler names to generic structural names
            "-metadata:s:v", "handler_name=",
            "-metadata:s:a", "handler_name=",
            "-metadata:s:s", "handler_name=",
        ])

    cmd.extend(["--", str(output_path)])

    res = run_command_secure(cmd, timeout_seconds=timeout)
    if res.timed_out:
        return False, f"Remux operation timed out after {timeout} seconds"

    if res.returncode != 0:
        err = res.stderr.strip()[-500:] if res.stderr else "Unknown FFmpeg error"
        return False, f"FFmpeg remux failed with code {res.returncode}: {err}"

    if not output_path.exists() or output_path.stat().st_size == 0:
        return False, "FFmpeg completed but output file is missing or zero-byte"

    return True, "Lossless remux completed successfully"


def reencode_video_fallback(
    input_path: Path,
    output_path: Path,
    format_hint: str = "mp4",
    options: RemovalOptions | None = None,
    timeout: int = DEFAULT_COMMAND_TIMEOUT,
) -> tuple[bool, str]:
    """Re-encode video with visually transparent CRF 18 settings when remuxing is impossible."""
    ffmpeg = get_ffmpeg_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i", str(input_path),
        "-map_metadata", "-1",
        "-map_chapters", "-1",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "veryfast",
        "-c:a", "copy",
        "-movflags", "+faststart",
        "--",
        str(output_path),
    ]

    res = run_command_secure(cmd, timeout_seconds=timeout)
    if res.timed_out:
        return False, f"Re-encode timed out after {timeout} seconds"

    if res.returncode != 0:
        err = res.stderr.strip()[-500:] if res.stderr else "Re-encode failed"
        return False, f"FFmpeg re-encode failed: {err}"

    if not output_path.exists() or output_path.stat().st_size == 0:
        return False, "Re-encode completed but output is empty"

    return True, "Re-encode fallback completed successfully"


# Alias for unified pipeline naming
clean_video_reencode = reencode_video_fallback
