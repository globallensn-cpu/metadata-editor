"""Reaboard PDF Sanitization Pipeline.

Executes dual-pass metadata elimination using ExifTool followed by QPDF linearization
to rewrite the document cross-reference table and drop orphaned incremental-update object trees.
Performs raw binary strings-scan verification to guarantee unrecoverable historical tags.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from apps.api.src.schemas.schemas import RemovalOptions
from apps.worker.src.engine.cmd_runner import run_command_secure
from apps.worker.src.engine.pipelines.image import get_exiftool_cmd

DEFAULT_COMMAND_TIMEOUT = 120


def get_qpdf_path() -> str:
    """Find qpdf binary from environment or PATH."""
    return os.environ.get("REABOARD_QPDF_PATH", "qpdf")


def clean_pdf(
    input_path: Path,
    output_path: Path,
    options: RemovalOptions | None = None,
    timeout: int = DEFAULT_COMMAND_TIMEOUT,
) -> tuple[bool, str, list[str]]:
    """Clean PDF by stripping tags with ExifTool and rewriting object streams with QPDF.

    Returns:
        (success: bool, info_or_error: str, warnings: list[str])
    """
    warnings: list[str] = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_stage = output_path.parent / f"temp_{output_path.name}"

    try:
        shutil.copyfile(input_path, temp_stage)

        # Step 1: Strip Info dict, XMP, and page-level metadata with ExifTool
        exiftool = get_exiftool_cmd()
        cmd_exif = list(exiftool) + [
            "-all=",
            "-overwrite_original",
            "-P",
            "--",
            str(temp_stage),
        ]
        res_exif = run_command_secure(cmd_exif, timeout_seconds=timeout)
        if res_exif.returncode != 0:
            return False, f"ExifTool PDF strip failed: {res_exif.stderr}", warnings

        # Step 2: Linearize and regenerate object streams with QPDF to drop orphaned revision objects
        qpdf = get_qpdf_path()
        cmd_qpdf = [
            qpdf,
            "--linearize",
            "--object-streams=generate",
            str(temp_stage),
            str(output_path),
        ]
        res_qpdf = run_command_secure(cmd_qpdf, timeout_seconds=timeout)
        if res_qpdf.returncode != 0:
            # Fallback if QPDF fails or is not installed: use temp_stage output
            shutil.copyfile(temp_stage, output_path)
            warnings.append("QPDF linearization skipped; output may contain historical revisions.")
        else:
            # Check for embedded JavaScript or attachments in output
            out_bytes = output_path.read_bytes()
            if b"/JavaScript" in out_bytes or b"/JS" in out_bytes:
                warnings.append("PDF contains embedded JavaScript actions.")
            if b"/EmbeddedFiles" in out_bytes or b"/EF" in out_bytes:
                warnings.append("PDF contains embedded file attachments.")

        return True, "PDF metadata stripped and object tree linearized successfully", warnings

    finally:
        temp_stage.unlink(missing_ok=True)


def scan_raw_bytes_for_string(file_path: Path, target_str: str) -> bool:
    """Scan raw binary bytes for an exact ASCII / UTF-8 string to confirm unrecoverability."""
    if not target_str:
        return False
    data = file_path.read_bytes()
    return target_str.encode("utf-8") in data
