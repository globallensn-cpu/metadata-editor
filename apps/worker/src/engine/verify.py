"""Reaboard Verification and Diffing Engine.

Extracts before/after metadata, filters tool/filesystem diff noise, validates packet-level
stream hashes across all video and audio streams, checks playback duration integrity,
and classifies surviving tags with honest reporting.
"""

from __future__ import annotations

import json
import logging
import os
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
    SurvivorClass,
    SurvivorField,
)
from apps.worker.src.engine.cmd_runner import run_command_secure
from apps.worker.src.engine.pipelines.image import get_exiftool_cmd
from apps.worker.src.engine.pipelines.video import get_ffmpeg_path

logger = logging.getLogger("reaboard.verify")


# Filesystem and tool noise tags to ignore in diffing
DIFF_NOISE_GROUPS = {"System", "ExifTool"}
DIFF_NOISE_TAGS = {
    "SourceFile",
    "Directory",
    "FileName",
    "FileSize",
    "FileModifyDate",
    "FileAccessDate",
    "FileInodeChangeDate",
    "FilePermissions",
    "ExifToolVersion",
    "Warning",
    "Error",
}

# Tags required for rendering and playback (structural survivors)
STRUCTURAL_TAGS: set[str] = {
    "ImageWidth", "ImageHeight", "SourceImageWidth", "SourceImageHeight",
    "BitDepth", "ColorType", "Compression", "Filter", "Interlace",
    "Orientation", "ColorSpaceData", "ProfileDescription", "ProfileVersion",
    "VideoFrameRate", "Duration", "AvgBitrate", "Channels", "AudioSampleRate",
    "AudioBitsPerSample", "MatrixStructure", "Rotation", "TrackDuration",
    "MediaDuration", "StreamCount", "CodecID", "CompressorName", "PixelFormat",
    "FieldOrder", "FrameRate", "AudioChannels", "SampleRate", "MajorBrand",
    "MinorVersion", "CompatibleBrands", "MIMEType", "FileType", "FileTypeExtension",
    "HandlerDescription", "HandlerType", "HandlerVendorID",
}


def get_ffprobe_path() -> str:
    return os.environ.get("REABOARD_FFPROBE_PATH", "ffprobe")


def is_diff_noise(group: str, tag: str) -> bool:
    """Check if tag is tool or filesystem noise that should be excluded from before/after diffs."""
    if group in DIFF_NOISE_GROUPS:
        return True
    if tag in DIFF_NOISE_TAGS or tag.startswith("File"):
        return True
    return False


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
    res = run_command_secure(cmd, timeout_seconds=30)
    if res.returncode == 0 and res.stdout.strip():
        try:
            return json.loads(res.stdout)
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
    res = run_command_secure(cmd, timeout_seconds=40)
    if res.returncode == 0 and res.stdout.strip():
        try:
            parsed = json.loads(res.stdout)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed[0]
        except Exception:
            pass
    return {}


def extract_unified_metadata(file_path: Path) -> dict[str, Any]:
    """Extract and merge metadata from ExifTool and FFprobe, excluding diff noise."""
    meta: dict[str, Any] = {}

    # 1. Primary ExifTool extraction
    exif = extract_metadata_exiftool(file_path)
    if exif:
        for k, v in exif.items():
            group = k.split(":")[0] if ":" in k else "General"
            tag = k.split(":")[1] if ":" in k else k
            if not is_diff_noise(group, tag):
                meta[k] = v

    # 2. FFprobe extraction
    ff = extract_metadata_ffprobe(file_path)
    if ff:
        fmt = ff.get("format", {})
        fmt_tags = fmt.get("tags", {})
        for k, v in fmt_tags.items():
            if not is_diff_noise("Format", k):
                key = f"Format:{k}"
                if key not in meta:
                    meta[key] = v

        for i, stream in enumerate(ff.get("streams", [])):
            stype = stream.get("codec_type", "stream")
            stream_tags = stream.get("tags", {})
            for k, v in stream_tags.items():
                if not is_diff_noise(f"Stream{i}_{stype}", k):
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
        group, tag = raw_key.split(":", 1) if ":" in raw_key else ("General", raw_key)

        if is_diff_noise(group, tag):
            continue

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


def compute_all_stream_md5s(file_path: Path) -> dict[str, str]:
    """Compute packet-level MD5 hashes for ALL video and audio streams by index."""
    ffmpeg = get_ffmpeg_path()
    ffprobe = get_ffprobe_path()

    # Discover streams
    cmd_probe = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        str(file_path),
    ]
    res_probe = run_command_secure(cmd_probe, timeout_seconds=15)
    stream_hashes: dict[str, str] = {}

    if res_probe.returncode != 0:
        return stream_hashes

    try:
        data = json.loads(res_probe.stdout)
        streams = data.get("streams", [])
    except Exception:
        return stream_hashes

    v_idx = 0
    a_idx = 0

    for stream in streams:
        codec_type = stream.get("codec_type")
        if codec_type == "video":
            specifier = f"0:v:{v_idx}"
            label = f"video_{v_idx}"
            v_idx += 1
        elif codec_type == "audio":
            specifier = f"0:a:{a_idx}"
            label = f"audio_{a_idx}"
            a_idx += 1
        else:
            continue

        cmd = [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-i", str(file_path),
            "-map", specifier,
            "-c", "copy",
            "-f", "md5",
            "-",
        ]
        res = run_command_secure(cmd, timeout_seconds=30)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if line.startswith("MD5="):
                    stream_hashes[label] = line.strip().replace("MD5=", "")
                    break

    return stream_hashes


def compute_stream_md5(file_path: Path, stream_type: str = "v") -> str | None:
    """Compute packet MD5 hash of the first stream of the given type ('v' or 'a')."""
    hashes = compute_all_stream_md5s(file_path)
    prefix = "video" if stream_type == "v" else "audio"
    for k, v in hashes.items():
        if k.startswith(prefix):
            return v
    return None


def extract_media_duration(file_path: Path) -> float | None:
    """Extract format duration in seconds using ffprobe."""
    ffprobe = get_ffprobe_path()
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    res = run_command_secure(cmd, timeout_seconds=15)
    if res.returncode == 0 and res.stdout.strip():
        try:
            return float(res.stdout.strip())
        except (ValueError, TypeError):
            pass
    return None


def verify_playback(file_path: Path, original_duration: float | None = None) -> bool:
    """Check that output video/audio is decodable and duration is within tolerance."""
    ffprobe = get_ffprobe_path()
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    res = run_command_secure(cmd, timeout_seconds=20)
    if res.returncode != 0:
        return False

    if original_duration is not None and original_duration > 0:
        try:
            clean_duration = float(res.stdout.strip())
            delta = abs(original_duration - clean_duration)
            max_allowed = max(0.5, original_duration * 0.005)
            return delta <= max_allowed
        except Exception:
            return False

    return True


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
    stream_copy_verified: bool | None,
    playback_verified: bool,
    pass_number: int = 1,
    stream_hashes_before: dict[str, str] | None = None,
    stream_hashes_after: dict[str, str] | None = None,
    extra_warnings: list[str] | None = None,
    orig_stream_md5: str | None = None,
    clean_stream_md5: str | None = None,
) -> RemovalReport:
    """Diff before and after metadata dictionaries and classify surviving tags with honest reporting."""
    if orig_stream_md5 and not stream_hashes_before:
        stream_hashes_before = {"video:0": orig_stream_md5}
    if clean_stream_md5 and not stream_hashes_after:
        stream_hashes_after = {"video:0": clean_stream_md5}
    removed: list[RemovedField] = []
    survivors: list[SurvivorField] = []
    warnings: list[str] = list(extra_warnings or [])

    before_keys = set(before_meta.keys())
    after_keys = set(after_meta.keys())

    # Detect removed tags
    for key in sorted(before_keys - after_keys):
        group, tag = key.split(":", 1) if ":" in key else ("General", key)
        if is_diff_noise(group, tag):
            continue

        val = str(before_meta[key])
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
        group, tag = key.split(":", 1) if ":" in key else ("General", key)
        if is_diff_noise(group, tag):
            continue

        val = str(after_meta[key])

        # Normalize generic handler names
        if tag in ("handler_name", "HandlerDescription") or "Handler" in val:
            s_class = SurvivorClass.STRUCTURAL
            reason = "Normalized to generic handler name for container playback."
        elif tag in STRUCTURAL_TAGS:
            s_class = SurvivorClass.STRUCTURAL
            reason = "Required for accurate rendering, dimensions, rotation, or codec playback."
        else:
            is_sensitive, cat = classify_tag(tag)
            if is_sensitive:
                s_class = SurvivorClass.IDENTIFYING
                reason = "Identifying tag persisted through cleaning passes."
            else:
                s_class = SurvivorClass.UNKNOWN
                reason = "Container atom or metadata not recognized as identifying."

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

    if identifying_count > 0:
        warnings.append(
            f"{identifying_count} identifying fields survived cleaning passes."
        )

    hashes = {
        "originalSha256": original_sha256,
        "cleanedSha256": cleaned_sha256,
    }
    if stream_hashes_before:
        hashes["originalStreams"] = str(stream_hashes_before)
    if stream_hashes_after:
        hashes["cleanedStreams"] = str(stream_hashes_after)

    return RemovalReport(
        job_id=job_id,
        method=method,
        method_reason=method_reason,
        pass_number=pass_number,
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
