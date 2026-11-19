"""Reaboard Image Sanitization Pipeline.

Executes atomic metadata stripping for JPEG, PNG, WebP, HEIC/HEIF, and TIFF images.
Preserves ICC Color Profile and Orientation tags when requested.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from apps.api.src.schemas.schemas import RemovalOptions
from apps.worker.src.engine.cmd_runner import run_command_secure

DEFAULT_COMMAND_TIMEOUT = 120


def get_exiftool_cmd() -> list[str]:
    """Retrieve ExifTool command array from environment or system path."""
    env_tool = os.environ.get("REABOARD_EXIFTOOL_PATH")
    if env_tool:
        return [env_tool]

    # Check for local portable perl/exiftool.pl if available
    tools_dir = Path(__file__).resolve().parents[5] / "tools" / "bin" / "exiftool_files"
    perl_exe = tools_dir / "perl.exe"
    exiftool_pl = tools_dir / "exiftool.pl"
    if perl_exe.exists() and exiftool_pl.exists():
        return [str(perl_exe), str(exiftool_pl)]

    which = shutil.which("exiftool")
    if which:
        return [which]

    return ["exiftool"]


def clean_image(
    input_path: Path,
    output_path: Path,
    detected_type: str,
    options: RemovalOptions | None = None,
    timeout: int = DEFAULT_COMMAND_TIMEOUT,
) -> tuple[bool, str]:
    """Strip image metadata on an isolated copy of the input file.

    Returns:
        (success: bool, error_message_or_info: str)
    """
    opts = options or RemovalOptions()
    exiftool = get_exiftool_cmd()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(input_path, output_path)

    cmd = list(exiftool) + [
        "-all=",
        "-overwrite_original",
        "-P",
    ]

    # Re-apply structural tags if configured
    if opts.keep_icc_profile:
        cmd.extend(["-tagsfromfile", "@", "-ICC_Profile"])
    if opts.keep_orientation:
        cmd.extend(["-tagsfromfile", "@", "-Orientation"])

    cmd.extend(["--", str(output_path)])

    res = run_command_secure(cmd, timeout_seconds=timeout)
    if res.timed_out:
        return False, f"ExifTool operation timed out after {timeout} seconds"

    if res.returncode != 0:
        err = res.stderr.strip()[-500:] if res.stderr else res.stdout.strip()[-500:]
        return False, f"ExifTool strip failed with code {res.returncode}: {err}"

    if not output_path.exists() or output_path.stat().st_size == 0:
        return False, "ExifTool completed but output file is missing or zero-byte"

    return True, "Image metadata sanitized successfully"
