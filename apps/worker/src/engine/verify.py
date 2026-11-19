"""Reaboard Verification and Diffing Engine.

Extracts before/after metadata, calculates packet-level stream MD5 hashes,
validates container playback integrity, and builds verified removal reports.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from apps.api.src.core.sensitive_fields import classify_tag, mask_sensitive_value
from apps.api.src.schemas.schemas import (
    CleaningMethod,
    MetadataField,
    MetadataReport,
    MetadataSection,
    RemovalReport,
    RemovedField,
    SensitivityCategory,
    SurvivorClass,
    SurvivorField,
)
from apps.worker.src.engine.pipelines.image import get_exiftool_cmd
from apps.worker.src.engine.pipelines.video import get_ffmpeg_path


STRUCTURAL_TAGS: set[str] = {
    # Video & Dimensions
    "ImageWidth", "ImageHeight", "SourceImageWidth", "SourceImageHeight",
    "BitDepth", "ColorType", "Compression", "Filter", "Interlace",
    "Orientation", "ColorSpaceData", "ProfileDescription", "ProfileVersion",
    "VideoFrameRate", "Duration", "AvgBitrate", "Channels", "AudioSampleRate",
    "AudioBitsPerSample", "MatrixStructure", "Rotation", "TrackDuration",
    "MediaDuration", "StreamCount", "CodecID", "CompressorName", "PixelFormat",
    "FieldOrder", "FrameRate", "AudioChannels", "SampleRate", "MajorBrand",
    "MinorVersion", "CompatibleBrands", "MIMEType", "FileType", "FileTypeExtension",
}


def get_ffprobe_path() -> str:
    return os.environ.get("REABOARD_FFPROBE_PATH", "ffprobe")


def extract_metadata_ffprobe(file_path: Path) -> dict[str, Any]:
    """Extract format, streams, and tags using ffprobe in JSON format."""
    ffprobe = get_ffprobe_path()
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        "-show_chapters",
        str(file_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=False)
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
    except Exception:
        pass
    return {}


def extract_metadata_exiftool(file_path: Path) -> dict[str, Any]:
    """Extract comprehensive metadata using ExifTool with group names (-G1)."""
    exiftool = get_exiftool_cmd()
    cmd = list(exiftool) + [
        "-j",
        "-G1",
        "-a",
        "-u",
        "-struct",
        "--",
        str(file_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=False)
        if proc.returncode == 0 and proc.stdout.strip():
            parsed = json.loads(proc.stdout)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed[0]
    except Exception:
        pass
    return {}


def extract_unified_metadata(file_path: Path) -> dict[str, Any]:
    """Extract and merge metadata from ExifTool and FFprobe."""
    meta: dict[str, Any] = {}

    # 1. Primary ExifTool extraction
    exif = extract_metadata_exiftool(file_path)
    if exif:
        for k, v in exif.items():
            if k.lower() in ("sourcefile", "directory"):
                continue
            meta[k] = v

    # 2. FFprobe extraction for tags
    ff = extract_metadata_ffprobe(file_path)
    if ff:
        fmt = ff.get("format", {})
        fmt_tags = fmt.get("tags", {})
        for k, v in fmt_tags.items():
            key = f"Format:{k}"
            if key not in meta:
                meta[key] = v

        for i, stream in enumerate(ff.get("streams", [])):
            stype = stream.get("codec_type", "stream")
            stream_tags = stream.get("tags", {})
            for k, v in stream_tags.items():
                key = f"Stream{i}_{stype}:{k}"
                if key not in meta:
                    meta[key] = v

    return meta


def build_metadata_report(job_id: str, file_info: Any, raw_meta: dict[str, Any]) -> MetadataReport:
    """Build structured MetadataReport for View mode."""
    sections_map: dict[str, list[MetadataField]] = {}
    sensitive_counts: dict[str, int] = {}
    total_fields = 0

    for raw_key, raw_val in raw_meta.items():
        if ":" in raw_key:
            group, tag = raw_key.split(":", 1)
        else:
            group, tag = "General", raw_key

        val_str = str(raw_val)
        is_sensitive, category = classify_tag(tag)
        val_preview = mask_sensitive_value(category, val_str) if is_sensitive else val_str

        field = MetadataField(
            group=group,
            tag=tag,
            value=raw_val,
            value_preview=val_preview,
            sensitive=is_sensitive,
            category=category,
        )

        if group not in sections_map:
            sections_map[group] = []
        sections_map[group].append(field)
        total_fields += 1

        if is_sensitive and category:
            cat_name = category.value
            sensitive_counts[cat_name] = sensitive_counts.get(cat_name, 0) + 1

    sections: list[MetadataSection] = []
    for group_name, fields in sorted(sections_map.items()):
        sens_count = sum(1 for f in fields if f.sensitive)
        sections.append(
            MetadataSection(
                name=group_name,
                field_count=len(fields),
                sensitive_count=sens_count,
                fields=fields,
            )
        )

    return MetadataReport(
        job_id=job_id,
        file_info=file_info,
        sections=sections,
        total_fields=total_fields,
        sensitive_summary=sensitive_counts,
    )


def compute_stream_md5(file_path: Path, stream_type: str = "v") -> str | None:
    """Compute MD5 of video/audio elementary stream packets to confirm lossless remux."""
    ffmpeg = get_ffmpeg_path()
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-i", str(file_path),
        "-map", f"0:{stream_type}:0",
        "-c", "copy",
        "-f", "md5",
        "-",
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30, shell=False)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if line.startswith("MD5="):
                    return line.strip().replace("MD5=", "")
    except Exception:
        pass
    return None


def verify_playback(file_path: Path, original_duration: float | None = None) -> bool:
    """Check that output video/audio can be parsed and duration is within 0.5% tolerance."""
    ffprobe = get_ffprobe_path()
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20, shell=False)
        if proc.returncode != 0:
            return False
        if original_duration is not None and original_duration > 0:
            duration = float(proc.stdout.strip())
            delta = abs(original_duration - duration)
            return delta <= max(0.5, original_duration * 0.005)
        return True
    except Exception:
        return False


def build_removal_report(
    job_id: str,
    method: CleaningMethod,
    method_reason: str,
    before_meta: dict[str, Any],
    after_meta: dict[str, Any],
    before_size: int,
    after_size: int,
    original_sha256: str,
    cleaned_sha256: str,
    stream_copy_verified: bool,
    playback_verified: bool,
    orig_stream_md5: str | None = None,
    clean_stream_md5: str | None = None,
) -> RemovalReport:
    """Diff before and after metadata dictionaries and classify surviving tags."""
    removed: list[RemovedField] = []
    survivors: list[SurvivorField] = []

    before_keys = set(before_meta.keys())
    after_keys = set(after_meta.keys())

    # Detect removed tags
    for key in sorted(before_keys - after_keys):
        val = str(before_meta[key])
        group, tag = key.split(":", 1) if ":" in key else ("General", key)
        is_sensitive, cat = classify_tag(tag)
        removed.append(
            RemovedField(
                group=group,
                tag=tag,
                value_preview=mask_sensitive_value(cat, val) if is_sensitive else val,
                category=cat,
            )
        )

    # Detect and classify survivors
    for key in sorted(after_keys):
        val = str(after_meta[key])
        group, tag = key.split(":", 1) if ":" in key else ("General", key)

        if tag in STRUCTURAL_TAGS:
            s_class = SurvivorClass.STRUCTURAL
            reason = "Required for accurate rendering, dimensions, rotation, or codec playback"
        else:
            is_sensitive, cat = classify_tag(tag)
            if is_sensitive:
                s_class = SurvivorClass.IDENTIFYING
                reason = "Identifying tag persisted through primary cleaning pass"
            else:
                s_class = SurvivorClass.UNKNOWN
                reason = "Container atom or metadata not recognized as identifying"

        survivors.append(
            SurvivorField(
                group=group,
                tag=tag,
                survivor_class=s_class,
                value_preview=val if s_class == SurvivorClass.STRUCTURAL else mask_sensitive_value(None, val),
                reason=reason,
            )
        )

    identifying_count = sum(1 for s in survivors if s.survivor_class == SurvivorClass.IDENTIFYING)
    structural_count = sum(1 for s in survivors if s.survivor_class == SurvivorClass.STRUCTURAL)
    unknown_count = sum(1 for s in survivors if s.survivor_class == SurvivorClass.UNKNOWN)

    warnings: list[str] = []
    if identifying_count > 0:
        warnings.append(f"{identifying_count} identifying fields survived cleaning.")

    hashes = {
        "originalSha256": original_sha256,
        "cleanedSha256": cleaned_sha256,
    }
    if orig_stream_md5:
        hashes["originalStreamMd5"] = orig_stream_md5
    if clean_stream_md5:
        hashes["cleanedStreamMd5"] = clean_stream_md5

    return RemovalReport(
        job_id=job_id,
        method=method,
        method_reason=method_reason,
        size_before=before_size,
        size_after=after_size,
        playback_verified=playback_verified,
        stream_copy=stream_copy_verified,
        removed=removed,
        survivors=survivors,
        warnings=warnings,
        counts={
            "removed": len(removed),
            "survivorsIdentifying": identifying_count,
            "survivorsStructural": structural_count,
            "survivorsUnknown": unknown_count,
        },
        hashes=hashes,
    )
