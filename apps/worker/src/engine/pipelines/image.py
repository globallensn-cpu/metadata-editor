"""Reaboard Image Sanitization Pipeline.

Executes atomic metadata stripping for JPEG, PNG, WebP, HEIC/HEIF, and TIFF images.
Preserves ICC Color Profile and Orientation tags when requested.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from apps.api.src.schemas.schemas import RemovalOptions


DEFAULT_COMMAND_TIMEOUT = 120


def get_exiftool_cmd() -> list[str]:
    """Retrieve ExifTool command array from environment or system path."""
    env_tool = os.environ.get("REABOARD_EXIFTOOL_PATH")
    if env_tool:
        return [env_tool]

    # Check for local windows portable exiftool
    local_perl = Path("D:/code metadata/tools/bin/exiftool_files/perl.exe")
    local_pl = Path("D:/code metadata/tools/bin/exiftool_files/exiftool.pl")
    if local_perl.exists() and local_pl.exists():
        return [str(local_perl), str(local_pl)]

    return ["exiftool"]


def clean_image(
    input_path: Path,
    output_path: Path,
    detected_type: str,
    options: RemovalOptions | None = None,
    timeout: int = DEFAULT_COMMAND_TIMEOUT,
) -> tuple[bool, str]:
    """Strip image metadata on a fresh copy of the input file.

    Returns:
        (success: bool, error_message_or_info: str)
    """
    opts = options or RemovalOptions()
    exiftool = get_exiftool_cmd()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Never modify input in place: copy original first
    shutil.copyfile(input_path, output_path)

    cmd = list(exiftool) + [
        "-all=",
        "-overwrite_original",
        "-P",  # Preserve file modification date/time if needed by filesystem
    ]

    # Re-apply structural tags if configured
    if opts.keep_icc_profile:
        cmd.extend(["-tagsfromfile", "@", "-ICC_Profile"])
    if opts.keep_orientation:
        cmd.extend(["-tagsfromfile", "@", "-Orientation"])

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
            err = proc.stderr.strip()[-500:] if proc.stderr else proc.stdout.strip()[-500:]
            return False, f"ExifTool strip failed with code {proc.returncode}: {err}"

        if not output_path.exists() or output_path.stat().st_size == 0:
            return False, "ExifTool completed but output file is missing or zero-byte"

        return True, "Image metadata sanitized successfully"

    except subprocess.TimeoutExpired:
        return False, f"ExifTool operation timed out after {timeout} seconds"
    except Exception as e:
        return False, f"Unexpected error executing ExifTool: {str(e)}"
